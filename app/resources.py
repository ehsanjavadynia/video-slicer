import asyncio
import io
import logging
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from .service import CapacityError, VideoService

logger = logging.getLogger(__name__)


class VideoResource:
    """FastAPI route handlers for video upload, download, and ZIP export."""

    def __init__(self, service: VideoService, path_validator, uploads_dir: Path):
        self.service = service
        self.path_validator = path_validator
        self.uploads_dir = uploads_dir
        self.router = APIRouter()
        self.router.add_api_route("/api/upload", self.upload, methods=["POST"])
        self.router.add_api_route(
            "/api/download/{job_id}/{filename}", self.download_clip, methods=["GET"]
        )
        self.router.add_api_route("/api/zip/{job_id}", self.download_zip, methods=["GET"])

    async def upload(
        self,
        video: UploadFile = File(...),
        maxDuration: str = Form(...),
        quality: str = Form("720"),
        compression: str = Form("0"),
    ):
        """Upload a video and split it into clips."""
        job_id = str(uuid.uuid4())
        job_dir = self.uploads_dir / job_id

        try:
            try:
                max_duration, quality_val, compression_val, ext = self.service.validate_params(
                    maxDuration, quality, compression, video.content_type, video.filename
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

            try:
                input_path = await self.service.save_upload(video, job_dir, ext)
            except OverflowError:
                raise HTTPException(status_code=413, detail="File too large")
            except IOError as e:
                raise HTTPException(status_code=500, detail=str(e))

            try:
                result = await self.service.process_upload(
                    job_id, input_path, job_dir, max_duration, quality_val, compression_val
                )
            except CapacityError as e:
                if job_dir.exists():
                    shutil.rmtree(job_dir, ignore_errors=True)
                raise HTTPException(status_code=429, detail=str(e))
            except RuntimeError:
                raise HTTPException(status_code=500, detail="Video processing failed")

            return {"jobId": job_id, **result}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in upload for job {job_id}: {e}")
            raise HTTPException(status_code=500, detail="An unexpected error occurred")

    async def download_clip(self, job_id: str, filename: str):
        """Download a single clip by filename."""
        try:
            filepath = self.path_validator.validate_job_path(job_id, filename)
            if not filepath.exists():
                raise HTTPException(status_code=404, detail="File not found")
            return FileResponse(
                path=filepath,
                filename=filename,
                media_type="application/octet-stream",
            )
        except ValueError as e:
            logger.warning(f"Invalid request for {job_id}/{filename}: {e}")
            raise HTTPException(status_code=400, detail="Invalid request")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error downloading clip {job_id}/{filename}: {e}")
            raise HTTPException(status_code=500, detail="Unable to download file")

    async def download_zip(self, job_id: str):
        """Download all clips for a job as a ZIP archive."""
        try:
            job_dir = self.path_validator.validate_job_path(job_id)

            if not job_dir.exists():
                raise HTTPException(status_code=404, detail="Job not found")

            clips = [f for f in job_dir.iterdir() if f.name.startswith("clip_")]
            if not clips:
                raise HTTPException(status_code=404, detail="No clips found for this job")

            def create_zip_in_thread():
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                    for clip_file in clips:
                        try:
                            zf.write(clip_file, arcname=clip_file.name)
                        except FileNotFoundError:
                            logger.warning(f"Clip file not found during ZIP: {clip_file.name}")
                buffer.seek(0)
                return buffer.getvalue()

            try:
                # asyncio.wait_for cannot cancel threads, so skip the wrapper and just await.
                data = await asyncio.to_thread(create_zip_in_thread)
            except Exception as e:
                logger.error(f"Error creating ZIP for job {job_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to create ZIP archive")

            # Reset cleanup timer after ZIP data is ready — starts the 10-minute window
            # from the point data is fully built, not from when the thread was launched.
            self.service.cleanup_manager.schedule_cleanup(job_id)
            logger.info(f"ZIP prepared for job {job_id}")
            return Response(
                content=data,
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="video_clips.zip"'},
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating ZIP for job {job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create ZIP archive")
