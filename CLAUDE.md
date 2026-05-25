# CLAUDE.md - Video Slicer Project Guide

## Project Overview

**Video Slicer** is a web application for splitting large video files into smaller, manageable clips with adjustable quality and compression settings.

- **Tech Stack**: Python 3 / FastAPI backend, vanilla JavaScript frontend, FFmpeg for video processing
- **Main Entry**: `server.py` (runs on port 3000 via uvicorn)
- **Frontend**: `public/index.html`, `public/app.js`, `public/style.css`
- **Configuration**: `constants.py` (centralized constants)
- **Tests**: `tests/test_server.py` (24 pytest tests, run with `pytest tests/ -v`)

## Architecture & Design Decisions

### Video Processing Pipeline
- Uses **asyncio.create_subprocess_exec** to invoke FFmpeg directly (no wrapper dependency)
- H.264 codec (libx264) for video, AAC for audio
- **CRF (Constant Rate Factor)** mapping for compression levels 0-6 (CRF 15-32)
  - Lower CRF = higher quality, larger files
  - CRF values defined in `constants.py`, shared between server and tests
- Processes clips **sequentially** (one at a time) to prevent resource exhaustion
- Each clip processed via non-blocking async subprocess (event loop not blocked)
- Default: 480p quality, Level 0 compression (maximum quality)

### Security Hardening (3-Round Review Completed)

**Python/FastAPI Migration Security:**
- Path traversal protection: `Path.resolve()` + `startswith()` boundary check in `validate_job_path()`
- File upload validation: 500MB limit (streaming check), video/* MIME type whitelist
- XSS prevention: Frontend still uses `textContent` for dynamic display
- Input validation: maxDuration bounds (1 - 3600 seconds), type coercion with error handling
- HTTP error handling: FastAPI's HTTPException for clean error responses
- FFmpeg process tracking: Dict of lists per job_id for signal cleanup
- Concurrent job limiting: `asyncio.Semaphore(3)` atomic gate + dict-based job tracking
- Request timeout: 30 minutes per clip (via `asyncio.wait_for`)
- jobId validation: UUID regex check + path traversal boundary validation
- Cleanup mechanism: `asyncio.get_event_loop().call_later()` + retry with exponential backoff
- Signal handlers: `signal.signal(SIGTERM/SIGINT)` with graceful FFmpeg process shutdown

## Key Files & Their Roles

| File | Purpose |
|------|---------|
| `server.py` | FastAPI server, FFmpeg processing via asyncio.create_subprocess_exec, API endpoints (POST /api/upload, GET /api/download, GET /api/zip), job management, cleanup, signal handlers |
| `constants.py` | Centralized configuration (CRF mapping, limits, timeouts in seconds) |
| `public/app.js` | Frontend form handling, API calls, results display, accessibility |
| `public/index.html` | HTML structure with ARIA labels for accessibility |
| `public/style.css` | Styling (no changes needed) |
| `tests/test_server.py` | 24 pytest tests covering validation, CRF mapping, calculations (6 test classes) |
| `requirements.txt` | Python dependencies (fastapi, uvicorn, python-multipart, aiofiles, pytest, httpx) |
| `run.sh` | Startup script: checks Python 3, creates/activates venv, installs requirements, runs uvicorn |
| `.gitignore` | Excludes uploads, __pycache__, *.pyc, venv, .pytest_cache, .DS_Store, *.log, .claude/ |

## API Endpoints

### POST /api/upload
Upload and split a video file.
- **Params**: `video` (file), `maxDuration` (seconds), `quality` (480/720/1080), `compression` (0-6)
- **Limits**: 100MB file size max, concurrent jobs max 3
- **Response**: `{ jobId, clips, totalDuration, chunkCount }`
- **Errors**: 400 (validation), 413 (file too large), 429 (too many jobs), 500 (processing)

### GET /api/download/:jobId/:filename
Download individual clip.
- **Security**: Path validated with `path.basename()` and `path.resolve()`
- **Files**: Stored in `uploads/{jobId}/clip_*.mp4`

### GET /api/zip/:jobId
Download all clips as ZIP archive.
- **Error Handling**: Checks headers before responding, gracefully closes on error
- **Cleanup**: Scheduled 10 minutes after download starts

## Working with Code

### Running the Project
```bash
./run.sh            # Start server on http://localhost:3000 (handles venv + dependencies)
# OR manually:
source venv/bin/activate && uvicorn server:app --port 3000

pytest tests/ -v    # Run 24 tests (all should pass)
```

### Making Changes

**When modifying core logic:**
1. Keep changes minimal and focused
2. If modifying validation/limits, update `constants.py` AND tests
3. Test with `pytest tests/ -v` - all 24 tests must pass
4. For FFmpeg changes: test with actual video files to verify encoding

**When adding features:**
1. Consider impact on concurrent job limits (3 max)
2. Ensure cleanup/resource management is in place
3. Add validation at system boundaries (user input, file uploads)
4. Update tests if adding new validation or constants
5. Add JSDoc comments for complex functions

**When fixing bugs:**
- Prefer minimal changes over refactoring surrounding code
- Update tests if the bug affects validation logic
- No backwards-compatibility hacks needed

### Testing
```bash
pytest tests/ -v    # Runs all 24 tests
```

Test categories:
- Input validation (maxDuration, quality, compression)
- CRF mapping (compression levels to CRF values)
- Quality levels (480p, 720p, 1080p)
- Duration calculations (chunk count, start times)
- Clip naming (zero-padding)
- Error handling (NaN, negative values, parsing)

All tests must pass before committing.

## Important Implementation Notes

### Static Files Mount Order (FastAPI Critical)
The static file mount **must be LAST** after all API routes, or it will intercept API calls:
```python
# ✅ CORRECT - mount static files last
@app.post("/api/upload")
async def upload(...): ...

@app.get("/api/download/{job_id}/{filename}")
async def download_clip(...): ...

app.mount("/", StaticFiles(directory="public"), name="static")  # LAST

# ❌ WRONG - mounting first causes /api/* routes to be intercepted
app.mount("/", StaticFiles(directory="public"), name="static")
@app.post("/api/upload")
async def upload(...): ...
```

### Cleanup Mechanism
- Scheduled via `asyncio.get_event_loop().call_later(delay, callback)` (Python equiv of setTimeout)
- Scheduled 10 minutes after upload or ZIP download completes
- Uses locks (`cleanup_locks` set) to prevent simultaneous scheduling
- Implements retry logic with exponential backoff (1s, 2s, 4s) via `_do_cleanup(job_id, retry)`
- Files in `uploads/{job_id}/` directory deleted via `shutil.rmtree()`
- ZIP downloads trigger cleanup via `schedule_cleanup(job_id)` in GET /api/zip/{job_id}

### Process Management
- FFmpeg processes tracked in `ffmpeg_processes[job_id]` dict of lists
- Each subprocess created via `asyncio.create_subprocess_exec()` with `await proc.wait()`
- Killed on error during split_video loop or via signal handlers
- Server handles SIGTERM/SIGINT via `signal.signal()` to gracefully kill all processes
- Timeout: 30 minutes per clip processing via `asyncio.wait_for(timeout=FFMPEG_TIMEOUT_SECONDS)`

### Rate Limiting & Concurrency
- Max 3 concurrent jobs via `asyncio.Semaphore(MAX_CONCURRENT_JOBS)`
- Request returns 429 if job count exceeds MAX_CONCURRENT_JOBS
- Jobs tracked in `active_jobs` dict for informational purposes
- No per-IP rate limiting (could be added if needed)

## Accessibility Notes

The project includes frontend accessibility improvements:
- File input button has `aria-label` and keyboard support (Enter/Space keys)
- Loading state has `role="status" aria-live="polite"` for announcements
- Error section has `role="alert" aria-live="assertive"` for alerts
- Clip items have `aria-label` for screen readers
- Download links have descriptive `aria-label` text

## Future Improvements (Not Yet Implemented)

Consider for future enhancements:
- Upload progress tracking with resumable uploads
- Per-IP or per-user rate limiting
- Video preview/thumbnail generation
- Quality presets (youtube, discord, etc.)
- Batch job queue system
- Metrics/observability for monitoring
- Database for job history
- Multi-file/playlist support

## Commit History & Releases

Latest commits are in reverse chronological order:
- **a7aeff7**: Add .claude directory to gitignore
- **92850f1**: Complete 3-round code review and improvement cycle (security + quality)
- **4af96bb**: Add comprehensive README with detailed documentation
- **28e75ff**: Set default compression to Level 0 (maximum quality)

Force push history has been cleaned (`.claude/` removed from all commits).

## Repository
- **GitHub**: https://github.com/ehsanjavadynia/video-slicer
- **Branch**: main
- **Status**: Production-ready with security hardening

---

**Last Updated**: May 2026
**Maintained By**: Claude (Haiku 4.5)
**Test Coverage**: 24 tests, all passing
**Status**: ✅ Ready for development
