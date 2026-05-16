#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎬 Video Slicer"
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg is not installed"
    echo "Installing ffmpeg with Homebrew..."
    brew install ffmpeg
    echo "✅ ffmpeg installed"
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo "✅ Dependencies installed"
fi

echo "🚀 Starting server..."
echo ""
echo "🌐 Open your browser at: http://localhost:3000"
echo "⏹️  Press Ctrl+C to stop the server"
echo ""

node server.js
