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


def expand_container_archive(path: Path) -> list[Path]:
    """
    Check if an archive is a multi-archive container (e.g. GoodMerge RAR/ZIP
    containing individual game .7z/.zip files). If so, extract sub-archives
    to a cache folder and return the list of extracted game archives.
    """
    ext = path.suffix.lower()
    if ext not in ARCHIVE_EXTENSIONS:
        return [path]

    from backend.config import settings
    import subprocess, shutil

    cache_base = settings.library_dir / "cache" / "extracted_sets"
    target_dir = cache_base / path.stem

    # 1. Try bsdtar for multi-volume RAR and zip containers (handles split RARs like Part1 and Part2)
    bsdtar_bin = shutil.which("bsdtar") or ("/usr/bin/bsdtar" if Path("/usr/bin/bsdtar").exists() else None)
    if bsdtar_bin and ext in (".rar", ".zip", ".tar", ".gz"):
        try:
            res = subprocess.run([bsdtar_bin, "-tf", str(path)], capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                sub_archives = [l for l in lines if Path(l).suffix.lower() in ARCHIVE_EXTENSIONS]
                if len(sub_archives) > 1:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    subprocess.run([bsdtar_bin, "-xf", str(path), "-C", str(target_dir)], check=True, timeout=180)
                    return sorted(p for p in target_dir.rglob("*.*") if p.is_file() and is_rom_file(p))
        except Exception as e:
            log.debug(f"bsdtar container expansion fallback for {path}: {e}")

    sub_archives: list[str] = []
    try:
        if ext == ".rar":
            import rarfile, re
            
            # Patch rarfile for [PartXofY] volume naming
            if not getattr(rarfile, "_part_patched", False):
                orig_next_newvol = rarfile._next_newvol
                def _patched_next_newvol(volfile):
                    m = re.search(r"\[Part(\d+)of(\d+)\]", volfile, re.IGNORECASE)
                    if m:
                        cur_part = int(m.group(1))
                        total_parts = m.group(2)
                        next_part = cur_part + 1
                        return volfile[:m.start(1)] + str(next_part) + volfile[m.end(1):]
                    return orig_next_newvol(volfile)
                rarfile._next_newvol = _patched_next_newvol
                rarfile._part_patched = True

            try:
                rf = rarfile.RarFile(path)
            except rarfile.NeedFirstVolume:
                # Continuation volume (e.g. Part2of2) already extracted by Part 1
                return []

            for info in rf.infolist():
                if not info.isdir() and Path(info.filename).suffix.lower() in ARCHIVE_EXTENSIONS:
                    sub_archives.append(info.filename)
            if len(sub_archives) > 1:
                target_dir = cache_base / path.stem
                target_dir.mkdir(parents=True, exist_ok=True)
                out_paths = []
                for info in rf.infolist():
                    if info.isdir():
                        continue
                    sub_file = target_dir / Path(info.filename).name
                    if not sub_file.exists() or sub_file.stat().st_size != info.file_size:
                        try:
                            data = rf.read(info)
                            sub_file.write_bytes(data)
                        except Exception:
                            pass
                    if sub_file.exists() and is_rom_file(sub_file):
                        out_paths.append(sub_file)
                return sorted(out_paths)
        elif ext == ".zip":
            import zipfile
            with zipfile.ZipFile(path, "r") as zf:
                for n in zf.namelist():
                    if not n.endswith("/") and Path(n).suffix.lower() in ARCHIVE_EXTENSIONS:
                        sub_archives.append(n)
                if len(sub_archives) > 1:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    out_paths = []
                    for n in zf.namelist():
                        if n.endswith("/"):
                            continue
                        sub_file = target_dir / Path(n).name
                        if not sub_file.exists():
                            try:
                                data = zf.read(n)
                                sub_file.write_bytes(data)
                            except Exception:
                                pass
                        if sub_file.exists() and is_rom_file(sub_file):
                            out_paths.append(sub_file)
                    return sorted(out_paths)
        elif ext == ".7z":
            import py7zr
            with py7zr.SevenZipFile(path, "r") as szf:
                for n in szf.getnames():
                    if Path(n).suffix.lower() in ARCHIVE_EXTENSIONS:
                        sub_archives.append(n)
                if len(sub_archives) > 1:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    szf.extractall(target_dir)
                    return sorted(p for p in target_dir.rglob("*.*") if p.is_file() and is_rom_file(p))
    except Exception as e:
        log.warning(f"Error expanding container archive {path}: {e}")

    return [path]


def _collect_files(source_dir: Path) -> list[Path]:
    results = []
    try:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file() and is_rom_file(path):
                # Expand container archives (GoodMerge sets, multi-game archives)
                expanded = expand_container_archive(path)
                results.extend(expanded)
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
