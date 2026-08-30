@echo off
REM RomOrganizer — Windows Launch Script
SET DIR=%~dp0
cd /d "%DIR%"

echo ==================================
echo   RomOrganizer v0.1.0
echo ==================================

if not exist ".venv" (
    echo Setting up Python virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -q -e .[dev]
) else (
    call .venv\Scripts\activate.bat
)

if not exist "frontend\dist" (
    echo Building frontend...
    cd frontend
    call npm install --silent
    call npm run build
    cd ..
)

echo.
echo Starting RomOrganizer at http://localhost:8765
echo Press Ctrl+C to stop.
echo.

start "" "http://localhost:8765"
uvicorn backend.main:app --host 127.0.0.1 --port 8765
