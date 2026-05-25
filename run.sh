#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Video Slicer"
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "ffmpeg is not installed"
    echo "Installing ffmpeg with Homebrew..."
    brew install ffmpeg
    echo "ffmpeg installed"
fi

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found"
    exit 1
fi

# Create venv if not present
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt
echo "Dependencies installed"

echo "Starting server..."
echo ""
echo "Open your browser at: http://localhost:3000"
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.server:app --host 0.0.0.0 --port 3000
