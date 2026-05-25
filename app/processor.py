import asyncio
import logging
import math
from pathlib import Path

from .constants import CRF_MAP

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Handles FFmpeg video processing: duration probing and clip encoding."""

    def __init__(self, registry, uploads_dir: Path):
        self.registry = registry
        self.uploads_dir = uploads_dir

    async def _probe_duration(self, input_path: Path) -> float:
        """Extract video duration via ffprobe. Raises RuntimeError on failure."""
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(input_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError("ffprobe failed to extract video duration")
        try:
            duration_str = stdout.decode().strip()
            if not duration_str:
                raise ValueError("Empty duration from ffprobe")
            return float(duration_str)
        except (ValueError, UnicodeDecodeError) as e:
            raise RuntimeError("Invalid video file: unable to extract duration") from e

    async def _encode_clip(self, job_id: str, cmd: list, clip_num: str) -> None:
        """Run a single FFmpeg encode command, tracking the process for cancellation."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        if job_id not in self.registry.ffmpeg_processes:
            self.registry.ffmpeg_processes[job_id] = []
        self.registry.ffmpeg_processes[job_id].append(proc)

        try:
            _, stderr_data = await proc.communicate()
            if proc.returncode != 0:
                if stderr_data:
                    logger.error(
                        f"FFmpeg error for clip {clip_num}: {stderr_data.decode(errors='replace')}"
                    )
                raise RuntimeError(f"FFmpeg failed with code {proc.returncode}")
        finally:
            # Always remove — whether success, error, or cancellation — so the split_video
            # finally block only sees genuinely still-running processes.
            try:
                self.registry.ffmpeg_processes[job_id].remove(proc)
            except (ValueError, KeyError):
                pass

    async def split_video(
        self,
        job_id: str,
        input_path: Path,
        output_dir: Path,
        max_duration: float,
        quality: int = 720,
        compression: int = 0,
    ) -> dict:
        """
        Split a video into sequential clips using FFmpeg.

        Returns:
            dict with clips (list), totalDuration (float), chunkCount (int)

        Raises:
            RuntimeError: if ffprobe or any clip encoding fails
        """
        total_duration = await self._probe_duration(input_path)
        chunk_count = math.ceil(total_duration / max_duration)
        clips = []
        ext = ".mp4"  # always H.264+AAC; WebM container rejects H.264

        try:
            for i in range(chunk_count):
                start_time = i * max_duration
                clip_num = str(i + 1).zfill(3)
                output_file = output_dir / f"clip_{clip_num}{ext}"
                crf = CRF_MAP.get(compression, 23)

                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(input_path),
                    "-ss", str(start_time),
                    "-t", str(max_duration),
                    "-c:v", "libx264",
                    "-crf", str(crf),
                    "-c:a", "aac",
                ]
                if quality in (480, 720, 1080):
                    cmd += ["-vf", f"scale=-2:{quality}"]
                cmd.append(str(output_file))

                await self._encode_clip(job_id, cmd, clip_num)
                clips.append(f"clip_{clip_num}{ext}")

            return {
                "clips": clips,
                "totalDuration": total_duration,
                "chunkCount": chunk_count,
            }
        finally:
            # Kill any still-running processes (e.g. on cancellation or error mid-loop)
            if job_id in self.registry.ffmpeg_processes:
                for p in self.registry.ffmpeg_processes[job_id]:
                    try:
                        p.kill()
                    except ProcessLookupError:
                        pass
            self.registry.ffmpeg_processes.pop(job_id, None)
