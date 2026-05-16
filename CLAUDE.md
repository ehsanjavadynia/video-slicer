# CLAUDE.md - Video Slicer Project Guide

## Project Overview

**Video Slicer** is a web application for splitting large video files into smaller, manageable clips with adjustable quality and compression settings.

- **Tech Stack**: Node.js/Express backend, vanilla JavaScript frontend, FFmpeg for video processing
- **Main Entry**: `server.js` (runs on port 3000)
- **Frontend**: `public/index.html`, `public/app.js`, `public/style.css`
- **Configuration**: `constants.js` (centralized constants)
- **Tests**: `tests/server.test.js` (24 tests, run with `npm test`)

## Architecture & Design Decisions

### Video Processing Pipeline
- Uses **fluent-ffmpeg** wrapper around FFmpeg for video encoding
- H.264 codec (libx264) for video, AAC for audio
- **CRF (Constant Rate Factor)** mapping for compression levels 0-6 (CRF 15-32)
  - Lower CRF = higher quality, larger files
  - CRF values defined in `constants.js`, shared between server and tests
- Processes clips **sequentially** (one at a time) to prevent resource exhaustion
- Default: 480p quality, Level 0 compression (maximum quality)

### Security Hardening (3-Round Review Completed)

**Round 1 - Critical Vulnerabilities Fixed:**
- Path traversal protection: `path.basename()` in download endpoints
- File upload validation: 100MB limit, video/* MIME type whitelist
- XSS prevention: Use `textContent` for dynamic filename display instead of `innerHTML`
- Input validation: maxDuration upper bound (3600 seconds/1 hour)
- HTTP error handling: Graceful error responses without header conflicts

**Round 2 - Resource Management:**
- FFmpeg process tracking and graceful shutdown on error/signals
- Concurrent job limiting: Max 3 active jobs (429 response when exceeded)
- Request timeout: 30 minutes per clip processing
- jobId path validation: UUID/safe format check + `path.resolve()` boundary validation
- Race condition prevention: Cleanup locks and retry logic with exponential backoff

**Round 3 - Code Quality:**
- JSDoc comments on complex functions (`splitVideo`, `validateJobPath`, `scheduleCleanup`)
- Constants extraction to `constants.js` (CRF_MAP, VALID_QUALITIES, VALID_COMPRESSION_LEVELS, limits)
- Improved error handling: Cleanup with retry logic (3 attempts with backoff)
- Frontend accessibility: ARIA labels, keyboard navigation, live regions for screen readers

## Key Files & Their Roles

| File | Purpose |
|------|---------|
| `server.js` | Express server, FFmpeg processing, API endpoints, job management |
| `constants.js` | Centralized configuration (CRF mapping, limits, timeouts) |
| `public/app.js` | Frontend form handling, API calls, results display, accessibility |
| `public/index.html` | HTML structure with ARIA labels for accessibility |
| `public/style.css` | Styling (no changes needed typically) |
| `tests/server.test.js` | 24 unit tests covering validation, CRF mapping, calculations |
| `.gitignore` | Excludes node_modules, uploads, .DS_Store, *.log, .claude/ |

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
npm start           # Start dev server on http://localhost:3000
npm test            # Run 24 tests (all should pass)
```

### Making Changes

**When modifying core logic:**
1. Keep changes minimal and focused
2. If modifying validation/limits, update `constants.js` AND tests
3. Test with `npm test` - all tests must pass
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
npm test            # Runs all 24 tests
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

### FFmpeg Output Options
Must pass all options as **single array** to `outputOptions()`, not chained:
```javascript
// ✅ CORRECT
const options = ['-crf', String(crf), '-vf', `scale=-1:${height}`];
cmd.outputOptions(options);

// ❌ WRONG - causes exit code 187
cmd.outputOptions('-crf', String(crf));
cmd.outputOptions('-vf', `scale=-1:${height}`);
```

### Cleanup Mechanism
- Scheduled 10 minutes after upload completes
- Uses locks (`cleanupLocks` Set) to prevent simultaneous deletions
- Implements retry logic with exponential backoff (1s, 2s, 4s)
- Files in `uploads/{jobId}/` directory are automatically deleted
- ZIP downloads reschedule cleanup to 10 minutes after download initiation

### Process Management
- FFmpeg processes tracked in `ffmpegProcesses` Map
- Killed on error via `.on('error')` handler
- Server handles SIGTERM/SIGINT to gracefully shutdown all processes
- Timeout: 30 minutes per clip (multiply by chunk count for total)

### Rate Limiting
- Max 3 concurrent jobs (request returns 429 if exceeded)
- No per-IP rate limiting (could be added if needed)
- Jobs tracked in `activeJobs` Map

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
