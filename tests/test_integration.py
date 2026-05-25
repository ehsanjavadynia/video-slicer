"""
Integration tests that run real FFmpeg processing against the test video files
in the project root. These tests are slower than the unit tests in test_server.py
because they invoke ffprobe/ffmpeg against actual video data.

Test videos:
  test-480p-explicit.mp4  — 10 s, 640×480, H.264+AAC
  test-plain.mp4          — 10 s, 1280×720, H.264+AAC
  test-video.mp4          — 60 s, 1280×720, H.264+AAC
  test-480p.mp4           — corrupted (moov atom missing) — used for error-path tests
  test-638s.mp4           — 638 s, 1280×720 — skipped (too slow for CI)
"""

import io
import shutil
import zipfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.server import app, uploads_dir

PROJECT_ROOT = Path(__file__).parent.parent

VIDEO_10S = PROJECT_ROOT / "test-480p-explicit.mp4"   # 10 s, 640×480
VIDEO_10S_B = PROJECT_ROOT / "test-plain.mp4"          # 10 s, 1280×720
VIDEO_60S = PROJECT_ROOT / "test-video.mp4"            # 60 s, 1280×720
VIDEO_CORRUPT = PROJECT_ROOT / "test-480p.mp4"         # corrupted


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """ASGI test client; triggers FastAPI startup/shutdown lifecycle."""
    uploads_dir.mkdir(exist_ok=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture(autouse=True)
async def cleanup_uploads():
    """Remove all upload directories created during a test."""
    yield
    if uploads_dir.exists():
        for folder in uploads_dir.iterdir():
            if folder.is_dir():
                shutil.rmtree(folder, ignore_errors=True)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def upload(client, video_path: Path, max_duration=5, quality=480, compression=0, timeout=120):
    with open(video_path, "rb") as f:
        return await client.post(
            "/api/upload",
            files={"video": (video_path.name, f, "video/mp4")},
            data={
                "maxDuration": str(max_duration),
                "quality": str(quality),
                "compression": str(compression),
            },
            timeout=timeout,
        )


# ---------------------------------------------------------------------------
# Validation tests (no FFmpeg invoked)
# ---------------------------------------------------------------------------

class TestUploadValidation:

    async def test_missing_video_field_returns_422(self, client):
        r = await client.post("/api/upload", data={"maxDuration": "10"})
        assert r.status_code == 422

    async def test_zero_max_duration_returns_400(self, client):
        with open(VIDEO_10S, "rb") as f:
            r = await client.post(
                "/api/upload",
                files={"video": (VIDEO_10S.name, f, "video/mp4")},
                data={"maxDuration": "0", "quality": "480", "compression": "0"},
            )
        assert r.status_code == 400

    async def test_negative_max_duration_returns_400(self, client):
        with open(VIDEO_10S, "rb") as f:
            r = await client.post(
                "/api/upload",
                files={"video": (VIDEO_10S.name, f, "video/mp4")},
                data={"maxDuration": "-5", "quality": "480", "compression": "0"},
            )
        assert r.status_code == 400

    async def test_invalid_quality_returns_400(self, client):
        with open(VIDEO_10S, "rb") as f:
            r = await client.post(
                "/api/upload",
                files={"video": (VIDEO_10S.name, f, "video/mp4")},
                data={"maxDuration": "5", "quality": "360", "compression": "0"},
            )
        assert r.status_code == 400

    async def test_invalid_compression_returns_400(self, client):
        with open(VIDEO_10S, "rb") as f:
            r = await client.post(
                "/api/upload",
                files={"video": (VIDEO_10S.name, f, "video/mp4")},
                data={"maxDuration": "5", "quality": "480", "compression": "7"},
            )
        assert r.status_code == 400

    async def test_non_video_mime_type_returns_400(self, client):
        r = await client.post(
            "/api/upload",
            files={"video": ("test.txt", io.BytesIO(b"not a video"), "text/plain")},
            data={"maxDuration": "5", "quality": "480", "compression": "0"},
        )
        assert r.status_code == 400

    async def test_unsupported_extension_returns_400(self, client):
        r = await client.post(
            "/api/upload",
            files={"video": ("test.exe", io.BytesIO(b"not a video"), "video/mp4")},
            data={"maxDuration": "5", "quality": "480", "compression": "0"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Processing tests (invoke real FFmpeg)
# ---------------------------------------------------------------------------

class TestVideoProcessing:

    async def test_10s_video_splits_into_two_5s_clips(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        data = r.json()
        assert data["chunkCount"] == 2
        assert len(data["clips"]) == 2

    async def test_10s_video_single_clip_when_duration_exceeds_length(self, client):
        r = await upload(client, VIDEO_10S, max_duration=30)
        assert r.status_code == 200
        data = r.json()
        assert data["chunkCount"] == 1
        assert len(data["clips"]) == 1

    async def test_output_clips_are_always_mp4(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        for clip in r.json()["clips"]:
            assert clip.endswith(".mp4"), f"Expected .mp4 clip, got {clip}"

    async def test_clip_names_are_zero_padded(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        clips = r.json()["clips"]
        assert "clip_001.mp4" in clips
        assert "clip_002.mp4" in clips

    async def test_response_contains_job_id(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        assert "jobId" in r.json()

    async def test_total_duration_is_approximately_correct(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        assert r.json()["totalDuration"] == pytest.approx(10.0, abs=1.0)

    async def test_480p_quality_produces_clips(self, client):
        r = await upload(client, VIDEO_10S, max_duration=10, quality=480)
        assert r.status_code == 200
        assert r.json()["chunkCount"] == 1

    async def test_720p_quality_produces_clips(self, client):
        r = await upload(client, VIDEO_10S_B, max_duration=10, quality=720)
        assert r.status_code == 200
        assert r.json()["chunkCount"] == 1

    async def test_1080p_quality_produces_clips(self, client):
        r = await upload(client, VIDEO_10S, max_duration=10, quality=1080)
        assert r.status_code == 200
        assert r.json()["chunkCount"] == 1

    async def test_max_compression_level_6(self, client):
        r = await upload(client, VIDEO_10S, max_duration=10, compression=6)
        assert r.status_code == 200

    async def test_min_compression_level_0(self, client):
        r = await upload(client, VIDEO_10S, max_duration=10, compression=0)
        assert r.status_code == 200

    async def test_60s_video_splits_into_correct_count(self, client):
        """60 s video with 20 s clips → 3 clips."""
        r = await upload(client, VIDEO_60S, max_duration=20, timeout=180)
        assert r.status_code == 200
        data = r.json()
        assert data["chunkCount"] == 3
        assert len(data["clips"]) == 3

    async def test_corrupted_video_returns_500(self, client):
        with open(VIDEO_CORRUPT, "rb") as f:
            r = await client.post(
                "/api/upload",
                files={"video": (VIDEO_CORRUPT.name, f, "video/mp4")},
                data={"maxDuration": "5", "quality": "480", "compression": "0"},
                timeout=30,
            )
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# Download tests
# ---------------------------------------------------------------------------

class TestDownload:

    async def test_download_single_clip_returns_binary(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        data = r.json()
        clip_name = data["clips"][0]

        r2 = await client.get(f"/api/download/{data['jobId']}/{clip_name}", timeout=30)
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "application/octet-stream"
        assert len(r2.content) > 1000  # must contain actual video data

    async def test_download_all_clips_individually(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        data = r.json()

        for clip_name in data["clips"]:
            r2 = await client.get(
                f"/api/download/{data['jobId']}/{clip_name}", timeout=30
            )
            assert r2.status_code == 200

    async def test_download_nonexistent_clip_returns_404(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        job_id = r.json()["jobId"]
        r2 = await client.get(f"/api/download/{job_id}/clip_999.mp4")
        assert r2.status_code == 404

    async def test_download_path_traversal_rejected(self, client):
        r = await client.get("/api/download/../../etc/passwd/clip.mp4")
        assert r.status_code in (400, 404)

    async def test_download_zip_is_valid_archive(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        assert r.status_code == 200
        job_id = r.json()["jobId"]

        r2 = await client.get(f"/api/zip/{job_id}", timeout=60)
        assert r2.status_code == 200
        assert "zip" in r2.headers["content-type"]

        zf = zipfile.ZipFile(io.BytesIO(r2.content))
        names = zf.namelist()
        assert "clip_001.mp4" in names
        assert "clip_002.mp4" in names

    async def test_download_zip_contains_all_clips(self, client):
        r = await upload(client, VIDEO_10S, max_duration=5)
        data = r.json()
        r2 = await client.get(f"/api/zip/{data['jobId']}", timeout=60)
        zf = zipfile.ZipFile(io.BytesIO(r2.content))
        assert sorted(zf.namelist()) == sorted(data["clips"])

    async def test_download_zip_nonexistent_job_returns_404(self, client):
        r = await client.get("/api/zip/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404
