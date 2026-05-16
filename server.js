import express from 'express';
import multer from 'multer';
import archiver from 'archiver';
import ffmpeg from 'fluent-ffmpeg';
import { v4 as uuidv4 } from 'uuid';
import fs from 'fs/promises';
import { createReadStream } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import {
  CRF_MAP,
  VALID_QUALITIES,
  VALID_COMPRESSION_LEVELS,
  MAX_CONCURRENT_JOBS,
  FFmpeg_TIMEOUT_MS,
  DEFAULT_CLEANUP_DELAY_MS,
  MAX_FILE_SIZE,
  MAX_DURATION_SECONDS
} from './constants.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3000;

const uploadsDir = path.join(__dirname, 'uploads');
const jobTimers = new Map();
const ffmpegProcesses = new Map();
const activeJobs = new Map();
const cleanupLocks = new Set();

await fs.mkdir(uploadsDir, { recursive: true });

const storage = multer.diskStorage({
  destination: async (req, file, cb) => {
    const jobId = req.body.jobId || uuidv4();
    req.jobId = jobId;
    const dir = path.join(uploadsDir, jobId);
    await fs.mkdir(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname);
    cb(null, `input${ext}`);
  }
});

const fileFilter = (req, file, cb) => {
  if (file.mimetype.startsWith('video/')) {
    cb(null, true);
  } else {
    cb(new Error('Only video files are allowed'));
  }
};

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: MAX_FILE_SIZE }
});

app.use(express.static('public'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

/**
 * Splits a video file into multiple clips with optional quality and compression settings.
 *
 * @param {string} inputPath - Absolute path to the input video file
 * @param {string} outputDir - Directory where output clips will be saved
 * @param {number} maxDuration - Maximum duration per clip in seconds
 * @param {number} [quality=720] - Output resolution height (480, 720, or 1080)
 * @param {number} [compression=0] - Compression level 0-6 (0=max quality, 6=max compression)
 *
 * @returns {Promise<{clips: string[], totalDuration: number, chunkCount: number}>}
 *   Resolves with an object containing:
 *   - clips: Array of output filenames created
 *   - totalDuration: Total duration of input video in seconds
 *   - chunkCount: Number of clips created
 *
 * @throws {Error} Rejects if ffprobe fails, ffmpeg encoding fails, or any I/O error occurs.
 *   All spawned ffmpeg processes are cleaned up on error.
 */
const splitVideo = async (inputPath, outputDir, maxDuration, quality = 720, compression = 1) => {
  return new Promise((resolve, reject) => {
    ffmpeg.ffprobe(inputPath, async (err, metadata) => {
      if (err) return reject(err);

      const totalDuration = metadata.format.duration;
      const chunkCount = Math.ceil(totalDuration / maxDuration);
      const clips = [];
      const jobProcesses = [];

      try {
        for (let i = 0; i < chunkCount; i++) {
          const startTime = i * maxDuration;
          const clipNum = String(i + 1).padStart(3, '0');
          const ext = path.extname(inputPath);
          const outputFile = path.join(outputDir, `clip_${clipNum}${ext}`);

          await new Promise((resolveClip, rejectClip) => {
            const qualityMap = {
              480: 480,
              720: 720,
              1080: null
            };

            const crf = CRF_MAP[compression] || 23;
            const options = ['-crf', String(crf)];

            if (qualityMap[quality]) {
              options.push('-vf');
              options.push(`scale=-1:${qualityMap[quality]}`);
            }

            const cmd = ffmpeg(inputPath)
              .seekInput(startTime)
              .duration(maxDuration)
              .videoCodec('libx264')
              .audioCodec('aac')
              .outputOptions(options);

            cmd.output(outputFile)
              .on('end', () => {
                clips.push(`clip_${clipNum}${ext}`);
                resolveClip();
              })
              .on('error', (err) => {
                jobProcesses.forEach(proc => {
                  try {
                    proc.kill();
                  } catch (e) {
                    // Process may already be dead
                  }
                });
                rejectClip(err);
              })
              .run();

            const proc = cmd._ffmpegProc;
            if (proc) {
              jobProcesses.push(proc);
            }
          });
        }

        resolve({ clips, totalDuration, chunkCount });
      } catch (error) {
        jobProcesses.forEach(proc => {
          try {
            proc.kill();
          } catch (e) {
            // Process may already be dead
          }
        });
        reject(error);
      }
    });
  });
};

/**
 * Validates a job ID to ensure it is a non-empty string with safe characters.
 *
 * @param {*} jobId - The job ID to validate
 *
 * @returns {string} The validated jobId
 *
 * @throws {Error} Throws 'Invalid jobId' if jobId is falsy or not a string.
 *   Throws 'Invalid jobId format' if jobId contains invalid characters (must match /^[a-zA-Z0-9_-]+$/).
 */
const validateJobId = (jobId) => {
  if (!jobId || typeof jobId !== 'string') {
    throw new Error('Invalid jobId');
  }
  if (!/^[a-zA-Z0-9_-]+$/.test(jobId)) {
    throw new Error('Invalid jobId format');
  }
  return jobId;
};

/**
 * Validates and resolves a safe file path within a job directory.
 *
 * Ensures the requested path:
 * 1. Uses a valid jobId (alphanumeric, dash, underscore only)
 * 2. Contains only the filename if subPath is provided (no directory traversal)
 * 3. Resolves within the uploads directory (prevents path traversal attacks)
 *
 * @param {string} jobId - The job ID to validate and use as the base directory
 * @param {string} [subPath=''] - Optional filename to append (only basename is used)
 *
 * @returns {string} Absolute resolved path that is safe to access
 *
 * @throws {Error} Throws validation errors from validateJobId or 'Path traversal attempt detected'
 *   if the resolved path escapes the uploads directory.
 */
const validateJobPath = (jobId, subPath = '') => {
  const jobId_safe = validateJobId(jobId);
  let fullPath = path.join(uploadsDir, jobId_safe);
  if (subPath) {
    fullPath = path.join(fullPath, path.basename(subPath));
  }
  const resolved = path.resolve(fullPath);
  const uploadsDirResolved = path.resolve(uploadsDir);
  if (!resolved.startsWith(uploadsDirResolved)) {
    throw new Error('Path traversal attempt detected');
  }
  return resolved;
};

/**
 * Schedules a delayed cleanup of job files with retry logic and proper error handling.
 *
 * Features:
 * - Prevents duplicate cleanup attempts (via cleanupLocks)
 * - Cancels previous cleanup timers for the same jobId
 * - Ensures cleanupLocks is always removed (success or failure)
 * - Implements retry logic with exponential backoff on failure
 * - Provides detailed error logging with jobId and context
 *
 * @param {string} jobId - The job ID whose files should be cleaned up
 * @param {number} [delayMs=600000] - Delay in milliseconds before cleanup (default: 10 min)
 *
 * @returns {void}
 *
 * @throws {Error} Does not throw; errors are logged to console.error with jobId context.
 *   Cleanup is retried with exponential backoff on failure.
 */
const scheduleCleanup = (jobId, delayMs = DEFAULT_CLEANUP_DELAY_MS) => {
  if (cleanupLocks.has(jobId)) {
    return;
  }

  cleanupLocks.add(jobId);

  if (jobTimers.has(jobId)) {
    clearTimeout(jobTimers.get(jobId));
  }

  const timer = setTimeout(async () => {
    let retryCount = 0;
    const maxRetries = 3;
    const baseRetryDelay = 1000; // 1 second

    const attemptCleanup = async () => {
      try {
        const jobDir = path.join(uploadsDir, jobId);
        await fs.rm(jobDir, { recursive: true, force: true });
        console.log(`Cleanup completed for job ${jobId}`);
        jobTimers.delete(jobId);
        cleanupLocks.delete(jobId);
      } catch (err) {
        retryCount++;
        if (retryCount < maxRetries) {
          const delayBeforeRetry = baseRetryDelay * Math.pow(2, retryCount - 1);
          console.error(
            `Failed to clean up job ${jobId} (attempt ${retryCount}/${maxRetries}): ${err.message}. Retrying in ${delayBeforeRetry}ms...`
          );
          setTimeout(attemptCleanup, delayBeforeRetry);
        } else {
          console.error(
            `Failed to clean up job ${jobId} after ${maxRetries} attempts: ${err.message}. Manual cleanup may be required.`
          );
          cleanupLocks.delete(jobId);
          jobTimers.delete(jobId);
        }
      }
    };

    await attemptCleanup();
  }, delayMs);

  jobTimers.set(jobId, timer);
};

app.post('/api/upload', upload.single('video'), async (req, res) => {
  try {
    const { maxDuration, quality, compression } = req.body;
    const jobId = req.jobId;
    const inputPath = req.file.path;
    const jobDir = path.join(uploadsDir, jobId);

    if (activeJobs.size >= MAX_CONCURRENT_JOBS) {
      return res.status(429).json({ error: `Maximum ${MAX_CONCURRENT_JOBS} concurrent jobs exceeded` });
    }

    if (!maxDuration || isNaN(maxDuration) || maxDuration <= 0) {
      return res.status(400).json({ error: 'Invalid maxDuration' });
    }

    if (maxDuration > MAX_DURATION_SECONDS) {
      return res.status(400).json({ error: `maxDuration cannot exceed ${MAX_DURATION_SECONDS} seconds` });
    }

    const qualityValue = parseInt(quality) || 720;
    if (!VALID_QUALITIES.includes(qualityValue)) {
      return res.status(400).json({ error: 'Invalid quality' });
    }

    const compressionValue = parseInt(compression) || 0;
    if (!VALID_COMPRESSION_LEVELS.includes(compressionValue)) {
      return res.status(400).json({ error: 'Invalid compression level' });
    }

    activeJobs.set(jobId, { startTime: Date.now(), chunkCount: 0 });

    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('FFmpeg processing timeout')), FFmpeg_TIMEOUT_MS);
    });

    try {
      const result = await Promise.race([
        splitVideo(inputPath, jobDir, parseInt(maxDuration), qualityValue, compressionValue),
        timeoutPromise
      ]);

      activeJobs.delete(jobId);
      scheduleCleanup(jobId);
      res.json({ jobId, ...result });
    } catch (error) {
      activeJobs.delete(jobId);
      throw error;
    }
  } catch (error) {
    console.error('Upload error:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/download/:jobId/:filename', (req, res) => {
  try {
    const { jobId, filename } = req.params;
    const filepath = validateJobPath(jobId, filename);

    res.download(filepath, (err) => {
      if (err) {
        console.error('Download error:', err);
      }
    });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
});

app.get('/api/zip/:jobId', (req, res) => {
  try {
    const { jobId } = req.params;
    const jobDir = validateJobPath(jobId);

    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', 'attachment; filename="video_clips.zip"');

    const archive = archiver('zip', { zlib: { level: 9 } });

    archive.on('error', (err) => {
      console.error('Archive error:', err);
      if (!res.headersSent) {
        res.status(500).json({ error: err.message });
      } else {
        res.end();
      }
    });

    res.on('error', (err) => {
      console.error('Response error:', err);
      archive.destroy();
    });

    archive.pipe(res);

    (async () => {
      try {
        const files = await fs.readdir(jobDir);
        files.forEach((file) => {
          if (file.startsWith('clip_')) {
            const filepath = path.join(jobDir, file);
            archive.file(filepath, { name: file });
          }
        });

        await archive.finalize();
      } catch (err) {
        console.error('Failed to read job directory:', err);
        if (!res.headersSent) {
          res.status(500).json({ error: err.message });
        } else {
          archive.destroy();
        }
      }
    })();

    res.on('finish', () => {
      scheduleCleanup(jobId, DEFAULT_CLEANUP_DELAY_MS);
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

const server = app.listen(PORT, () => {
  console.log(`Video Slicer running at http://localhost:${PORT}`);
});

const killAllFFmpegProcesses = () => {
  ffmpegProcesses.forEach((processes) => {
    processes.forEach(proc => {
      try {
        proc.kill();
      } catch (e) {
        // Process may already be dead
      }
    });
  });
};

process.on('SIGTERM', () => {
  console.log('SIGTERM received, shutting down gracefully...');
  killAllFFmpegProcesses();
  jobTimers.forEach(timer => clearTimeout(timer));
  server.close(() => {
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  console.log('SIGINT received, shutting down gracefully...');
  killAllFFmpegProcesses();
  jobTimers.forEach(timer => clearTimeout(timer));
  server.close(() => {
    process.exit(0);
  });
});
