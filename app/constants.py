"""
Application constants for Video Slicer
"""

# CRF (Constant Rate Factor) mapping for compression levels
# Lower CRF = better quality, higher CRF = smaller file size
CRF_MAP = {
    0: 15,   # Maximum Quality (Largest file)
    1: 18,   # Very High Quality
    2: 21,   # High Quality
    3: 23,   # Balanced (Default)
    4: 25,   # Medium Compression
    5: 28,   # High Compression
    6: 32    # Maximum Compression (Smallest file)
}

# Valid output quality levels in pixels
VALID_QUALITIES = [480, 720, 1080]

# Valid compression levels
VALID_COMPRESSION_LEVELS = [0, 1, 2, 3, 4, 5, 6]

# Maximum concurrent jobs allowed
MAX_CONCURRENT_JOBS = 3

# FFmpeg processing timeout in seconds (30 minutes)
FFMPEG_TIMEOUT_SECONDS = 30 * 60

# Default cleanup delay in seconds (10 minutes)
DEFAULT_CLEANUP_DELAY_SECONDS = 10 * 60

# Maximum file upload size in bytes (500 MB)
MAX_FILE_SIZE = 500 * 1024 * 1024

# Maximum duration per clip in seconds
MAX_DURATION_SECONDS = 3600
