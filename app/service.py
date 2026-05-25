import asyncio
import logging
import shutil
from pathlib import Path

import aiofiles

from .constants import (
    FFMPEG_TIMEOUT_SECONDS,
    MAX_CONCURRENT_JOBS,
    MAX_DURATION_SECONDS,
    MAX_FILE_SIZE,
    VALID_COMPRESSION_LEVELS,
    VALID_QUALITIES,
)

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}


class CapacityError(Exception):
    """Raised when the server has reached its maximum concurrent job limit."""


class VideoService:
    """Encapsulates upload validation, file saving, and job processing orchestration."""

    def __init__(self, registry, video_processor, cleanup_manager, uploads_dir: Path):
        self.registry = registry
        self.video_processor = video_processor
        self.cleanup_manager = cleanup_manager
        self.uploads_dir = uploads_dir

    def validate_params(
        self,
        max_duration_str: str,
        quality_str: str,
        compression_str: str,
        content_type: str,
        filename: str,
    ) -> tuple:
        """
        Validate and parse upload parameters.

        Returns:
            (max_duration, quality, compression, ext) tuple of validated values

        Raises:
            ValueError: on invalid param values
        """
        try:
            max_duration = int(max_duration_str)
        except (ValueError, TypeError):
            raise ValueError("Invalid maxDuration")
        if max_duration <= 0:
            raise ValueError("Invalid maxDuration")
        if max_duration > MAX_DURATION_SECONDS:
            raise ValueError(f"maxDuration cannot exceed {MAX_DURATION_SECONDS} seconds")

        try:
            quality = int(quality_str)
        except (ValueError, TypeError):
            raise ValueError("Invalid quality")
        if quality not in VALID_QUALITIES:
            raise ValueError("Invalid quality")

        try:
            compression = int(compression_str)
        except (ValueError, TypeError):
            raise ValueError("Invalid compression level")
        if compression not in VALID_COMPRESSION_LEVELS:
            raise ValueError("Invalid compression level")

        if not content_type or not content_type.startswith("video/"):
            raise ValueError("Only video files are allowed")

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
            )

        return max_duration, quality, compression, ext

    async def save_upload(self, video, job_dir: Path, ext: str) -> Path:
        """
        Stream-save the uploaded file to disk with size enforcement.

        Returns:
            Path to the saved input file

        Raises:
            OverflowError: if upload exceeds MAX_FILE_SIZE (maps to HTTP 413)
            IOError: if the file is missing after save
        """
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / f"input{ext}"
        total_bytes = 0
        try:
            async with aiofiles.open(input_path, "wb") as f:
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    if total_bytes + len(chunk) > MAX_FILE_SIZE:
                        raise OverflowError("File too large")
                    await f.write(chunk)
                    total_bytes += len(chunk)
            if not input_path.exists():
                raise IOError("Input file not found after save")
        except Exception:
            # Clean up partial write for any failure (OverflowError, IOError, etc.)
            if job_dir.exists():
                shutil.rmtree(job_dir, ignore_errors=True)
            raise

        return input_path

    async def process_upload(
        self,
        job_id: str,
        input_path: Path,
        job_dir: Path,
        max_duration: int,
        quality: int,
        compression: int,
    ) -> dict:
        """
        Run video processing under the concurrency semaphore with job lifecycle tracking.

        Returns:
            dict with clips, totalDuration, chunkCount

        Raises:
            CapacityError: if the server is at max concurrent jobs
            RuntimeError: if FFmpeg processing fails
        """
        # Safe in single-threaded asyncio: no await point exists between this check
        # and active_jobs[job_id] = True inside the semaphore (semaphore.acquire()
        # does not suspend when a slot is free), so the check is effectively atomic.
        if len(self.registry.active_jobs) >= MAX_CONCURRENT_JOBS:
            raise CapacityError("Server is busy, please try again later")

        result: dict | None = None
        async with self.registry.semaphore:
            self.registry.active_jobs[job_id] = True
            try:
                result = await asyncio.wait_for(
                    self.video_processor.split_video(
                        job_id, input_path, job_dir, max_duration, quality, compression
                    ),
                    timeout=FFMPEG_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError as e:
                if job_dir.exists():
                    shutil.rmtree(job_dir, ignore_errors=True)
                logger.error(f"Job {job_id} timed out")
                raise RuntimeError("Video processing timed out") from e
            except Exception as e:
                if job_dir.exists():
                    shutil.rmtree(job_dir, ignore_errors=True)
                logger.error(f"Error processing job {job_id}: {e}")
                raise RuntimeError("Video processing failed") from e
            finally:
                self.registry.active_jobs.pop(job_id, None)

        if result is None:
            raise RuntimeError("Processing yielded no result")
        self.cleanup_manager.schedule_cleanup(job_id)
        logger.info(f"Successfully processed job {job_id}: {len(result['clips'])} clips")
        return result
