import asyncio

from .constants import MAX_CONCURRENT_JOBS


class JobRegistry:
    """Centralized registry for job state and process tracking."""

    def __init__(self):
        self.active_jobs: dict = {}           # job_id → True while processing
        self.ffmpeg_processes: dict = {}      # job_id → list[asyncio.subprocess.Process]
        self.job_timers: dict = {}            # job_id → asyncio.Task
        self.cleanup_locks: set = set()       # job_ids scheduled for cleanup
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
