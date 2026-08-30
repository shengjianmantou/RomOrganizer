"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.db.database import init_db
from backend.routers import export_jobs, import_jobs, library, settings, systems

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Initializing database...")
    init_db()
    log.info("RomOrganizer backend ready.")
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="RomOrganizer",
    description="Calibre-like ROM library manager for retro gaming",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8765"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(library.router)
app.include_router(systems.router)
app.include_router(import_jobs.router)
app.include_router(export_jobs.router)
app.include_router(settings.router)

# Serve media files (cover art, screenshots)
from backend.config import settings as cfg

@app.on_event("startup")
async def ensure_dirs():
    cfg.media_dir.mkdir(parents=True, exist_ok=True)
    (cfg.media_dir / "covers").mkdir(exist_ok=True)
    (cfg.media_dir / "screenshots").mkdir(exist_ok=True)

# Mount media at /media
media_path = cfg.media_dir
if media_path.exists():
    app.mount("/media", StaticFiles(directory=str(media_path)), name="media")

# Serve React frontend (built files)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
