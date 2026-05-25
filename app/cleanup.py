import asyncio
import logging
import shutil
import time
from pathlib import Path

from .constants import DEFAULT_CLEANUP_DELAY_SECONDS

logger = logging.getLogger(__name__)


class JobCleanupManager:
    """Manages job cleanup scheduling, retry logic, and periodic cleanup."""

    def __init__(self, registry, uploads_dir: Path):
        self.registry = registry
        self.uploads_dir = uploads_dir

    async def _do_cleanup(self, job_id: str, retry: int = 0) -> None:
        max_retries = 3
        base_delay = 1.0
        job_dir = self.uploads_dir / job_id
        if not job_dir.exists():
            self.registry.job_timers.pop(job_id, None)
            self.registry.cleanup_locks.discard(job_id)
            return
        try:
            shutil.rmtree(job_dir, ignore_errors=False)
            self.registry.job_timers.pop(job_id, None)
            self.registry.cleanup_locks.discard(job_id)
            self.registry.ffmpeg_processes.pop(job_id, None)
            logger.info(f"Cleanup completed for job {job_id}")
        except Exception as e:
            if retry < max_retries:
                wait = base_delay * (2 ** retry)
                logger.warning(
                    f"Failed to clean up job {job_id} (attempt {retry + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait}s..."
                )
                await asyncio.sleep(wait)
                await self._do_cleanup(job_id, retry + 1)
            else:
                logger.error(
                    f"Failed to clean up job {job_id} after {max_retries} attempts: {e}. "
                    f"Manual cleanup may be required."
                )
                self.registry.cleanup_locks.discard(job_id)
                self.registry.job_timers.pop(job_id, None)

    def schedule_cleanup(
        self, job_id: str, delay: float = DEFAULT_CLEANUP_DELAY_SECONDS
    ) -> None:
        if job_id in self.registry.job_timers:
            self.registry.job_timers[job_id].cancel()

        self.registry.cleanup_locks.add(job_id)
        logger.info(f"Cleanup scheduled for job {job_id} in {delay}s")

        async def cleanup_task():
            await asyncio.sleep(delay)
            await self._do_cleanup(job_id)

        task = asyncio.create_task(cleanup_task())
        self.registry.job_timers[job_id] = task

    async def periodic_cleanup_task(self) -> None:
        """Periodically removes old upload folders every 5 minutes."""
        while True:
            try:
                await asyncio.sleep(5 * 60)

                if not self.uploads_dir.exists():
                    continue

                current_time = time.time()
                removed_count = 0

                for job_folder in self.uploads_dir.iterdir():
                    if not job_folder.is_dir():
                        continue

                    job_id = job_folder.name
                    if job_id in self.registry.active_jobs:
                        continue
                    if job_id in self.registry.cleanup_locks:
                        continue

                    try:
                        folder_age = current_time - job_folder.stat().st_ctime
                        if folder_age > 15 * 60:
                            shutil.rmtree(job_folder, ignore_errors=True)
                            removed_count += 1
                            logger.info(f"Periodic cleanup: removed job folder {job_id}")
                    except Exception as e:
                        logger.warning(f"Error cleaning up {job_id}: {e}")

                if removed_count > 0:
                    logger.info(f"Periodic cleanup: removed {removed_count} old upload folders")

            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def shutdown(self) -> None:
        """Cancel all pending cleanup tasks on shutdown."""
        for handle in self.registry.job_timers.values():
            if isinstance(handle, asyncio.Task) and not handle.done():
                handle.cancel()
