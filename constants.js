/**
 * Application constants for Video Slicer
 */

// CRF (Constant Rate Factor) mapping for compression levels
// Lower CRF = better quality, higher CRF = smaller file size
export const CRF_MAP = {
  0: 15,   // Maximum Quality (Largest file)
  1: 18,   // Very High Quality
  2: 21,   // High Quality
  3: 23,   // Balanced (Default)
  4: 25,   // Medium Compression
  5: 28,   // High Compression
  6: 32    // Maximum Compression (Smallest file)
};

// Valid output quality levels in pixels
export const VALID_QUALITIES = [480, 720, 1080];

// Valid compression levels
export const VALID_COMPRESSION_LEVELS = [0, 1, 2, 3, 4, 5, 6];

// Maximum concurrent jobs allowed
export const MAX_CONCURRENT_JOBS = 3;

// FFmpeg processing timeout in milliseconds (30 minutes)
export const FFmpeg_TIMEOUT_MS = 30 * 60 * 1000;

// Default cleanup delay in milliseconds (10 minutes)
export const DEFAULT_CLEANUP_DELAY_MS = 10 * 60 * 1000;

// Maximum file upload size in bytes (100 MB)
export const MAX_FILE_SIZE = 100 * 1024 * 1024;

// Maximum duration per clip in seconds
export const MAX_DURATION_SECONDS = 3600;
