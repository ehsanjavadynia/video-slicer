#!/bin/bash

echo "⏹️  Stopping Video Slicer..."

# Kill process running on port 3000
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    lsof -Pi :3000 -sTCP:LISTEN -t | xargs kill -9
    echo "✅ Server stopped"
else
    echo "ℹ️  No server running on port 3000"
fi
