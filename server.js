import express from 'express';
import multer from 'multer';
import archiver from 'archiver';
import ffmpeg from 'fluent-ffmpeg';
import { v4 as uuidv4 } from 'uuid';
import fs from 'fs/promises';
import { createReadStream } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = 3000;

const uploadsDir = path.join(__dirname, 'uploads');
const jobTimers = new Map();

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

const upload = multer({ storage });

app.use(express.static('public'));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const splitVideo = async (inputPath, outputDir, maxDuration, quality = 720, compression = 1) => {
  return new Promise((resolve, reject) => {
    ffmpeg.ffprobe(inputPath, async (err, metadata) => {
      if (err) return reject(err);

      const totalDuration = metadata.format.duration;
      const chunkCount = Math.ceil(totalDuration / maxDuration);
      const clips = [];

      const crfMap = {
        0: 15,
        1: 18,
        2: 21,
        3: 23,
        4: 25,
        5: 28,
        6: 32
      };

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

            const crf = crfMap[compression] || 23;
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
              .on('error', rejectClip)
              .run();
          });
        }

        resolve({ clips, totalDuration, chunkCount });
      } catch (error) {
        reject(error);
      }
    });
  });
};

const scheduleCleanup = (jobId, delayMs = 10 * 60 * 1000) => {
  if (jobTimers.has(jobId)) {
    clearTimeout(jobTimers.get(jobId));
  }

  const timer = setTimeout(async () => {
    try {
      const jobDir = path.join(uploadsDir, jobId);
      await fs.rm(jobDir, { recursive: true, force: true });
      jobTimers.delete(jobId);
    } catch (err) {
      console.error(`Failed to clean up job ${jobId}:`, err);
    }
  }, delayMs);

  jobTimers.set(jobId, timer);
};

app.post('/api/upload', upload.single('video'), async (req, res) => {
  try {
    const { maxDuration, quality, compression } = req.body;
    const jobId = req.jobId;
    const inputPath = req.file.path;
    const jobDir = path.join(uploadsDir, jobId);

    if (!maxDuration || isNaN(maxDuration) || maxDuration <= 0) {
      return res.status(400).json({ error: 'Invalid maxDuration' });
    }

    const qualityValue = parseInt(quality) || 720;
    if (![480, 720, 1080].includes(qualityValue)) {
      return res.status(400).json({ error: 'Invalid quality' });
    }

    const compressionValue = parseInt(compression) || 3;
    if (![0, 1, 2, 3, 4, 5, 6].includes(compressionValue)) {
      return res.status(400).json({ error: 'Invalid compression level' });
    }

    const result = await splitVideo(inputPath, jobDir, parseInt(maxDuration), qualityValue, compressionValue);
    scheduleCleanup(jobId);

    res.json({ jobId, ...result });
  } catch (error) {
    console.error('Upload error:', error);
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/download/:jobId/:filename', (req, res) => {
  try {
    const { jobId, filename } = req.params;
    const filepath = path.join(uploadsDir, jobId, filename);

    res.download(filepath, (err) => {
      if (err) {
        console.error('Download error:', err);
      }
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/zip/:jobId', (req, res) => {
  try {
    const { jobId } = req.params;
    const jobDir = path.join(uploadsDir, jobId);

    res.setHeader('Content-Type', 'application/zip');
    res.setHeader('Content-Disposition', 'attachment; filename="video_clips.zip"');

    const archive = archiver('zip', { zlib: { level: 9 } });

    archive.on('error', (err) => {
      console.error('Archive error:', err);
      res.status(500).json({ error: err.message });
    });

    archive.pipe(res);

    fs.readdir(jobDir).then((files) => {
      files.forEach((file) => {
        if (file.startsWith('clip_')) {
          const filepath = path.join(jobDir, file);
          archive.file(filepath, { name: file });
        }
      });

      archive.finalize();
    }).catch((err) => {
      console.error('Failed to read job directory:', err);
      res.status(500).json({ error: err.message });
    });

    res.on('finish', () => {
      scheduleCleanup(jobId, 1000);
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.listen(PORT, () => {
  console.log(`Video Slicer running at http://localhost:${PORT}`);
});
