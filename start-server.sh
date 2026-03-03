#!/bin/bash
# Quick start script for local development

echo "Starting Cesar Transcription Server..."
echo "======================================"

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies if needed
if ! pip show faster-whisper > /dev/null 2>&1; then
    echo "Installing dependencies..."
    pip install -e .
fi

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  WARNING: FFmpeg not found!"
    echo "   YouTube transcription will not work."
    echo "   Install with: sudo apt install ffmpeg"
fi

# Create data directory
mkdir -p data

echo ""
echo "Starting server on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop"
echo ""

# Run server
python -m uvicorn cesar.api.server:app --host 0.0.0.0 --port 8000 --reload
