#!/bin/bash
# RomOrganizer — Main Launch Script
# Starts both the backend API and opens the browser.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=================================="
echo "  RomOrganizer v0.1.0"
echo "=================================="

# --- Backend setup ---
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3.11+ is required."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Setting up Python virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -q -e ".[dev]"
fi

# --- Frontend build check ---
if [ ! -d "frontend/dist" ]; then
    echo "Building frontend..."
    if command -v npm &>/dev/null; then
        cd frontend && npm install --silent && npm run build && cd ..
    else
        echo "WARNING: npm not found, frontend will not be built."
        echo "Run: cd frontend && npm install && npm run build"
    fi
fi

echo ""
echo "Starting RomOrganizer at http://localhost:8765"
echo "Press Ctrl+C to stop."
echo ""

# Open browser after a short delay
(sleep 2 && open "http://localhost:8765" 2>/dev/null || true) &

.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765
