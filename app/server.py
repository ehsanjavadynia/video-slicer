import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .cleanup import JobCleanupManager
from .processor import VideoProcessor
from .registry import JobRegistry
from .resources import VideoResource
from .service import VideoService
from .validator import PathValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PORT = 3000

# Paths are resolved relative to the project root (parent of the app/ package)
_root = Path(__file__).parent.parent
uploads_dir = _root / "uploads"
_public_dir = _root / "public"

# --- Dependency wiring ---
registry = JobRegistry()
path_validator = PathValidator(uploads_dir)
cleanup_manager = JobCleanupManager(registry, uploads_dir)
video_processor = VideoProcessor(registry, uploads_dir)
service = VideoService(registry, video_processor, cleanup_manager, uploads_dir)
video_resource = VideoResource(service, path_validator, uploads_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    uploads_dir.mkdir(exist_ok=True)
    periodic_task = asyncio.create_task(cleanup_manager.periodic_cleanup_task())
    logger.info(f"Video Slicer started on port {PORT}")
    logger.info("Periodic cleanup task started (runs every 5 minutes)")
    yield
    logger.info("Shutting down gracefully...")
    periodic_task.cancel()
    for procs in registry.ffmpeg_processes.values():
        for p in procs:
            try:
                p.kill()
            except ProcessLookupError:
                pass
    await cleanup_manager.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(title="Video Slicer", lifespan=lifespan)

app.include_router(video_resource.router)

# Mount static files LAST — after all API routes, or they intercept /api/* calls
app.mount("/", StaticFiles(directory=str(_public_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
