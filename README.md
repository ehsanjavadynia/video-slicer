# Video Slicer

A lightweight web application that splits large video files into smaller, more manageable clips with adjustable quality and compression settings.

## Features

- **Video Splitting**: Divide videos into clips of specified duration
- **Quality Control**: Choose from 3 resolution options (480p, 720p, 1080p)
- **7 Compression Levels**: Fine-grained control over file size vs. quality tradeoff using FFmpeg's CRF
- **Batch Download**: Download individual clips or all clips as a single ZIP file
- **Automatic Cleanup**: Temporary files are automatically cleaned up after 10 minutes
- **Simple UI**: Intuitive web interface with real-time feedback

## Tech Stack

- **Backend**: Python with FastAPI
- **ASGI Server**: Uvicorn
- **Video Processing**: FFmpeg via subprocess
- **File Upload**: python-multipart
- **Archiving**: zipfile (Python standard library)
- **Frontend**: Vanilla JavaScript, HTML, CSS
- **Video Codec**: H.264 (libx264)
- **Audio Codec**: AAC

## Installation

### Prerequisites

- Python 3.8 or higher
- FFmpeg installed and available in PATH

On macOS (via Homebrew):
```bash
brew install ffmpeg python3
```

On Ubuntu/Debian:
```bash
sudo apt-get install ffmpeg python3 python3-pip python3-venv
```

### Setup

1. Clone or download the repository
2. Run the startup script (handles venv and dependencies):
   ```bash
   ./run.sh
   ```

   Or manually:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.server:app --port 3000
   ```

3. Open your browser and navigate to `http://localhost:3000`

## Usage

### Web Interface

1. **Select Video**: Click "Choose a video..." to select a video file
2. **Configure Settings**:
   - **Max Clip Duration** (seconds): How long each clip should be
   - **Quality**: 480p (SD), 720p (HD), or 1080p (Full HD)
   - **Compression Level**: 0-6 scale (0 = maximum quality, 6 = maximum compression)
3. **Submit**: Click "Split Video" to process
4. **Download**: Once complete, download individual clips or all clips as a ZIP

### Compression Levels

| Level | CRF | Quality | Use Case |
|-------|-----|---------|----------|
| 0 | 15 | Visually Lossless | Archive, professional use |
| 1 | 18 | Very High | High-quality streaming |
| 2 | 21 | High | General use |
| 3 | 23 | Balanced | Default, good balance |
| 4 | 25 | Medium | Smaller files needed |
| 5 | 28 | High Compression | Mobile-friendly |
| 6 | 32 | Maximum Compression | Minimum file size |

**Note**: CRF (Constant Rate Factor) ranges from 0-51, where lower values mean higher quality and larger files. The default FFmpeg CRF is 23.

## API Endpoints

### POST /api/upload

Upload a video file and split it into clips.

**Parameters** (form-data):
- `video`: Video file (required)
- `maxDuration`: Maximum duration per clip in seconds (required, must be > 0)
- `quality`: Resolution in pixels (480, 720, or 1080; default: 720)
- `compression`: Compression level 0-6 (default: 0)

**Response**:
```json
{
  "jobId": "uuid-string",
  "clips": ["clip_001.mp4", "clip_002.mp4", ...],
  "totalDuration": 125.5,
  "chunkCount": 5
}
```

### GET /api/download/{jobId}/{filename}

Download a specific clip.

**Parameters**:
- `jobId`: Job ID from upload response
- `filename`: Clip filename (e.g., "clip_001.mp4")

**Response**: Binary file download

### GET /api/zip/{jobId}

Download all clips as a ZIP file.

**Parameters**:
- `jobId`: Job ID from upload response

**Response**: ZIP file download

## Configuration

### Default Settings

- Quality: 480p
- Compression: Level 0 (maximum quality, CRF 15)
- Server Port: 3000
- Auto-cleanup Delay: 10 minutes
- Max Upload Size: 500 MB (enforced during streaming upload)

### Environment Variables

Currently, no environment variables are required. To customize the server port, use:

```bash
uvicorn server:app --port 8000
```

To modify constants like compression levels or timeouts, edit `constants.py`.

## Development

### Project Structure

```
video-slicer/
├── app/                   # Python source package
│   ├── __init__.py
│   ├── server.py          # FastAPI app, startup/shutdown, dependency wiring
│   ├── registry.py        # JobRegistry — shared state (jobs, processes, timers)
│   ├── validator.py       # PathValidator — path traversal and symlink protection
│   ├── processor.py       # VideoProcessor — FFmpeg encoding and duration probing
│   ├── service.py         # VideoService — validation, file save, job orchestration
│   ├── cleanup.py         # JobCleanupManager — cleanup scheduling and periodic sweep
│   ├── resources.py       # VideoResource — FastAPI route handlers (APIRouter)
│   └── constants.py       # Shared constants (CRF mappings, limits, timeouts)
├── public/
│   ├── index.html         # Web UI
│   ├── app.js             # Frontend JavaScript
│   └── style.css          # Styling
├── tests/
│   ├── __init__.py
│   └── test_server.py     # 24 pytest tests
├── uploads/               # Temporary working directory (created at runtime)
├── requirements.txt       # Python dependencies
└── README.md
```

### How It Works

1. **Upload**: User selects a video file and configuration
2. **Processing**: Server uses FFmpeg to extract clips of specified duration
3. **Validation**: Each parameter is validated before processing
4. **Cleanup**: After 10 minutes (or after ZIP download), temporary files are deleted
5. **Download**: User can download clips individually or as ZIP

### FFmpeg Command Flow

For each clip:
```bash
ffmpeg -i input.mp4 -ss {startTime} -t {duration} \
  -c:v libx264 -crf {crfValue} -vf scale=-2:{height} \
  -c:a aac -y output.mp4
```

Where:
- `-ss`: Start seek time
- `-t`: Duration
- `-c:v`: Video codec (H.264)
- `-crf`: Quality level
- `-vf scale`: Resolution scaling (maintains aspect ratio)
- `-c:a`: Audio codec (AAC)

## Troubleshooting

### FFmpeg not found
Ensure FFmpeg is installed and in your system PATH.

### Video not splitting correctly
- Check that `maxDuration` is greater than 0
- Verify video file format is supported (MP4, MKV, AVI, MOV, etc.)
- Check server logs for FFmpeg error messages

### Files not downloading
- Browser must allow downloads for localhost:3000
- Check that job ID is valid and temporary files haven't been cleaned up

### High disk usage
- Clips are stored in the `uploads/` directory
- Automatic cleanup runs 10 minutes after processing
- To reduce disk usage, lower quality or increase compression level

## Performance Notes

- Processing time depends on video length and quality settings
- Higher quality settings require more disk space and time to process
- Processing happens sequentially (clips are created one at a time)
- For very long videos, consider using higher compression levels

## License

MIT

## Contributing

Feel free to submit issues and enhancement requests!

---

**Created**: May 2026
**Version**: 1.0.0
