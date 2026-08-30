"""
Directory scanner — discovers ROM files in one or more source directories.
Source directories are always read-only.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator

from backend.services.systems import EXTENSION_TO_SYSTEMS

log = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar"}

IGNORED_EXTENSIONS = {
    ".txt", ".nfo", ".jpg", ".jpeg", ".png", ".gif", ".xml",
    ".dat", ".cue", ".m3u", ".srm", ".sav", ".state", ".cfg",
    ".db", ".json", ".htm", ".html", ".md", ".pdf",
}


def is_rom_file(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in IGNORED_EXTENSIONS:
        return False
    return ext in EXTENSION_TO_SYSTEMS or ext in ARCHIVE_EXTENSIONS


async def scan_directory(source_dir: Path) -> AsyncIterator[Path]:
    """Recursively scan a directory for ROM files (async generator)."""
    if not source_dir.exists():
        log.warning(f"Source directory does not exist: {source_dir}")
        return
    loop = asyncio.get_event_loop()
    files = await loop.run_in_executor(None, _collect_files, source_dir)
    for f in files:
        yield f


def _collect_files(source_dir: Path) -> list[Path]:
    results = []
    try:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and is_rom_file(path):
                results.append(path)
    except PermissionError as e:
        log.warning(f"Permission denied scanning {source_dir}: {e}")
    return results


def count_rom_files(source_dir: Path) -> int:
    return len(_collect_files(source_dir))


def detect_system_from_path(path: Path) -> list[str]:
    """Return candidate ES-DE system folder names for a ROM file."""
    ext = path.suffix.lower()
    if ext in EXTENSION_TO_SYSTEMS:
        return EXTENSION_TO_SYSTEMS[ext]
    return []


def infer_system_from_directory(path: Path, esde_folders: set[str]) -> str | None:
    """Check if any path component or parent directory matches a known ES-DE folder."""
    for part in path.parts:
        norm = part.lower().strip()
        if norm in esde_folders:
            return norm
    return None


def detect_internal_extension(path: Path) -> str | None:
    """Inspect the extension of the first ROM file inside a ZIP/7z/RAR archive."""
    ext = path.suffix.lower()
    if ext == ".zip":
        try:
            import zipfile
            with zipfile.ZipFile(path, "r") as zf:
                for name in zf.namelist():
                    s = Path(name).suffix.lower()
                    if s in EXTENSION_TO_SYSTEMS:
                        return s
        except Exception:
            pass
    elif ext == ".7z":
        try:
            import py7zr
            with py7zr.SevenZipFile(path, "r") as szf:
                for name in szf.getnames():
                    s = Path(name).suffix.lower()
                    if s in EXTENSION_TO_SYSTEMS:
                        return s
        except Exception:
            pass
    elif ext == ".rar":
        try:
            import rarfile
            with rarfile.RarFile(path, "r") as rf:
                for item in rf.infolist():
                    s = Path(item.filename).suffix.lower()
                    if s in EXTENSION_TO_SYSTEMS:
                        return s
        except Exception:
            pass
    return None
