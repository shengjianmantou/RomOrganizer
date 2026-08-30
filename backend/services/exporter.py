"""
Export service — exports selected games to an ES-DE-compatible directory,
handles deduplication, language priority, compression, gamelist.xml generation,
and bundling a portable copy of the app.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator
from xml.etree import ElementTree as ET

from backend.config import settings
from backend.db.database import get_session
from backend.db.models import ExportJob, Game, RomFile, System
from backend.services.filename_parser import parse_rom_filename

log = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
MANIFEST_DIR = "RomOrganizer"

# In-memory progress queues keyed by job_id
_export_queues: dict[int, asyncio.Queue] = {}


def get_export_queue(job_id: int) -> asyncio.Queue:
    if job_id not in _export_queues:
        _export_queues[job_id] = asyncio.Queue()
    return _export_queues[job_id]


async def stream_export_progress(job_id: int) -> AsyncIterator[dict]:
    q = get_export_queue(job_id)
    while True:
        event = await q.get()
        yield event
        if event.get("status") in ("done", "error"):
            break


async def start_export(job_id: int) -> None:
    """Main export coroutine — runs in background."""
    q = get_export_queue(job_id)

    def emit(event: dict):
        asyncio.get_event_loop().call_soon_threadsafe(q.put_nowait, event)

    with get_session() as session:
        job = session.get(ExportJob, job_id)
        if not job:
            return
        job.status = "running"
        session.commit()
        game_ids = json.loads(job.game_ids)
        export_dir = Path(job.export_dir)
        output_format = job.output_format
        dedup_mode = job.dedup_mode
        lang_priority = [l.strip() for l in job.lang_priority.split(",")]

    try:
        export_dir.mkdir(parents=True, exist_ok=True)

        # Load existing manifest to avoid overwriting
        manifest = _load_manifest(export_dir)
        existing_hashes: set[str] = set(manifest.get("sha1_hashes", []))
        existing_hashes.update(manifest.get("md5_hashes", []))

        # Gather games
        with get_session() as session:
            games = session.query(Game).filter(Game.id.in_(game_ids)).all()
            # Eagerly load relationships
            games_data = []
            for g in games:
                system = g.system
                rom_files = list(g.rom_files)
                games_data.append((g, system, rom_files))

        total = len(games_data)
        with get_session() as session:
            job = session.get(ExportJob, job_id)
            job.total_games = total
            session.commit()

        emit({"type": "total", "total": total})

        exported = skipped = errors = 0

        # Group by (title_normalized, system) for dedup in "single" mode
        if dedup_mode == "single":
            groups: dict[tuple[str, int], list[tuple[Game, System, list[RomFile]]]] = {}
            for g, sys_, roms in games_data:
                key = (_normalize_title(g.title), sys_.id)
                groups.setdefault(key, []).append((g, sys_, roms))

            deduped: list[tuple[Game, System, list[RomFile]]] = []
            for group_items in groups.values():
                best = _pick_best_version(group_items, lang_priority)
                deduped.append(best)
            to_export = deduped
        else:
            to_export = games_data

        # Gamelist data per system
        gamelists: dict[str, list[dict]] = {}

        for g, sys_, rom_files in to_export:
            try:
                if not rom_files:
                    skipped += 1
                    continue

                rom_file = rom_files[0]
                src_path = settings.library_dir / rom_file.library_path

                # Skip if already in manifest
                if (rom_file.sha1 and rom_file.sha1 in existing_hashes) or \
                   (rom_file.md5 and rom_file.md5 in existing_hashes):
                    skipped += 1
                    emit({"type": "progress", "exported": exported, "skipped": skipped, "errors": errors, "total": total})
                    continue

                # Determine output path
                dest_system_dir = export_dir / "roms" / sys_.esde_folder
                dest_system_dir.mkdir(parents=True, exist_ok=True)

                loop = asyncio.get_event_loop()
                dest_filename = await loop.run_in_executor(
                    None, _write_rom, src_path, dest_system_dir, output_format
                )

                if dest_filename:
                    # Track in manifest
                    if rom_file.sha1:
                        existing_hashes.add(rom_file.sha1)
                    if rom_file.md5:
                        existing_hashes.add(rom_file.md5)

                    # Build gamelist entry
                    gamelists.setdefault(sys_.esde_folder, []).append({
                        "game": g,
                        "filename": dest_filename,
                        "system": sys_,
                    })
                    exported += 1
                else:
                    errors += 1

                emit({"type": "progress", "exported": exported, "skipped": skipped, "errors": errors, "total": total})

            except Exception as e:
                log.warning(f"Export error for game {g.id}: {e}")
                errors += 1

        # Write gamelist.xml per system
        loop = asyncio.get_event_loop()
        for esde_folder, entries in gamelists.items():
            gl_path = export_dir / "roms" / esde_folder / "gamelist.xml"
            await loop.run_in_executor(
                None, _write_gamelist_xml, gl_path, entries, esde_folder
            )

        # Update manifest
        manifest["sha1_hashes"] = list(existing_hashes)
        manifest["exported_at"] = datetime.now(timezone.utc).isoformat()
        manifest["total_exported"] = manifest.get("total_exported", 0) + exported
        _save_manifest(export_dir, manifest)

        # Bundle app copy
        await loop.run_in_executor(None, _bundle_app, export_dir)

        with get_session() as session:
            job = session.get(ExportJob, job_id)
            job.status = "done"
            job.finished_at = datetime.now(timezone.utc)
            job.exported_games = exported
            job.skipped_games = skipped
            job.errors = errors
            session.commit()

        emit({"type": "done", "status": "done", "exported": exported, "skipped": skipped, "errors": errors})

    except Exception as e:
        log.exception(f"Export job {job_id} failed: {e}")
        with get_session() as session:
            job = session.get(ExportJob, job_id)
            job.status = "error"
            job.finished_at = datetime.now(timezone.utc)
            job.log = str(e)
            session.commit()
        emit({"type": "error", "status": "error", "message": str(e)})
    finally:
        await asyncio.sleep(60)
        _export_queues.pop(job_id, None)


def _normalize_title(title: str) -> str:
    """Normalize title for grouping (lowercase, strip articles)."""
    t = title.lower().strip()
    for article in ("the ", "a ", "an "):
        if t.startswith(article):
            t = t[len(article):]
    return t


def _pick_best_version(
    group: list[tuple[Game, System, list[RomFile]]],
    lang_priority: list[str],
) -> tuple[Game, System, list[RomFile]]:
    """From a group of same-title games, pick best by language priority."""
    def score(item):
        g, _, _ = item
        langs = [l.strip() for l in (g.languages or "").split(",") if l.strip()]
        parsed = parse_rom_filename(g.title)
        parsed.languages = langs or parsed.languages
        pri_score = parsed.lang_priority_score(lang_priority)
        # Prefer non-special (no Beta/Demo/Proto)
        special_penalty = 100 if parsed.is_special else 0
        return (special_penalty + pri_score,)

    return min(group, key=score)


def _write_rom(src_path: Path, dest_dir: Path, output_format: str) -> str | None:
    """Write a ROM to dest_dir in the desired format. Returns dest filename or None."""
    try:
        if output_format == "original" or output_format == src_path.suffix.lower().lstrip("."):
            dest = dest_dir / src_path.name
            if not dest.exists():
                shutil.copy2(str(src_path), str(dest))
            return src_path.name

        elif output_format == "zip":
            dest_name = src_path.stem + ".zip"
            dest = dest_dir / dest_name
            if not dest.exists():
                _compress_to_zip(src_path, dest)
            return dest_name

        elif output_format == "7z":
            dest_name = src_path.stem + ".7z"
            dest = dest_dir / dest_name
            if not dest.exists():
                _compress_to_7z(src_path, dest)
            return dest_name

        else:
            # Fallback: copy as-is
            dest = dest_dir / src_path.name
            if not dest.exists():
                shutil.copy2(str(src_path), str(dest))
            return src_path.name

    except Exception as e:
        log.warning(f"Failed to write ROM {src_path}: {e}")
        return None


def _compress_to_zip(src: Path, dest: Path) -> None:
    """Compress src ROM file into a ZIP archive."""
    # If src is already a zip, copy as-is
    if src.suffix.lower() == ".zip":
        shutil.copy2(str(src), str(dest))
        return
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(src, src.name)


def _compress_to_7z(src: Path, dest: Path) -> None:
    """Compress src ROM file into a 7z archive."""
    if src.suffix.lower() == ".7z":
        shutil.copy2(str(src), str(dest))
        return
    import py7zr
    with py7zr.SevenZipFile(dest, mode="w") as szf:
        szf.write(src, src.name)


def _write_gamelist_xml(
    gamelist_path: Path,
    entries: list[dict],
    esde_folder: str,
) -> None:
    """Write or merge an ES-DE gamelist.xml file."""
    # Load existing gamelist if present
    existing_paths: set[str] = set()
    if gamelist_path.exists():
        try:
            tree = ET.parse(str(gamelist_path))
            root = tree.getroot()
            for game_el in root.findall("game"):
                path_el = game_el.find("path")
                if path_el is not None and path_el.text:
                    existing_paths.add(path_el.text)
        except Exception:
            root = ET.Element("gameList")
    else:
        root = ET.Element("gameList")

    for entry in entries:
        g: Game = entry["game"]
        filename: str = entry["filename"]
        rom_path_str = f"./{filename}"

        if rom_path_str in existing_paths:
            continue

        game_el = ET.SubElement(root, "game")
        _xml_sub(game_el, "path", rom_path_str)
        _xml_sub(game_el, "name", g.title)
        if g.description:
            _xml_sub(game_el, "desc", g.description)
        if g.release_year:
            _xml_sub(game_el, "releasedate", f"{g.release_year}0101T000000")
        if g.developer:
            _xml_sub(game_el, "developer", g.developer)
        if g.publisher:
            _xml_sub(game_el, "publisher", g.publisher)
        if g.genre:
            _xml_sub(game_el, "genre", g.genre)
        if g.players:
            _xml_sub(game_el, "players", str(g.players))
        if g.rating is not None:
            _xml_sub(game_el, "rating", f"{g.rating:.2f}")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    gamelist_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(gamelist_path), encoding="utf-8", xml_declaration=True)


def _xml_sub(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el


def _load_manifest(export_dir: Path) -> dict:
    manifest_path = export_dir / MANIFEST_DIR / MANIFEST_FILENAME
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except Exception:
            pass
    return {"sha1_hashes": [], "md5_hashes": [], "total_exported": 0}


def _save_manifest(export_dir: Path, manifest: dict) -> None:
    manifest_dir = export_dir / MANIFEST_DIR
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest, indent=2))


def _bundle_app(export_dir: Path) -> None:
    """Copy the application source into the export directory."""
    bundle_dir = export_dir / MANIFEST_DIR
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Copy backend
    src_backend = Path(__file__).parent.parent  # backend/
    dest_backend = bundle_dir / "backend"
    if not dest_backend.exists():
        shutil.copytree(str(src_backend), str(dest_backend),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # Copy pyproject.toml
    pyproject = src_backend.parent / "pyproject.toml"
    if pyproject.exists():
        shutil.copy2(str(pyproject), str(bundle_dir / "pyproject.toml"))

    # Write launch scripts
    _write_launch_scripts(bundle_dir)


def _write_launch_scripts(bundle_dir: Path) -> None:
    """Write start.sh and start.bat inside the bundled app directory."""
    sh_content = """#!/bin/bash
# RomOrganizer — Launch Script
# Run this script to start the ROM organizer for THIS export directory.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LIBRARY_DIR="$(dirname "$DIR")"

cd "$DIR"
if ! command -v python3 &>/dev/null; then
    echo "Python 3 is required. Please install Python 3.11+."
    exit 1
fi

# Create venv if not present
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -e .
fi

LIBRARY_DIR="$LIBRARY_DIR" .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765 --reload
"""
    bat_content = """@echo off
REM RomOrganizer — Launch Script
SET DIR=%~dp0
SET LIBRARY_DIR=%DIR%..

cd /d "%DIR%"
python -m venv .venv 2>nul || echo Using existing venv
call .venv\\Scripts\\activate.bat
pip install -q -e . 2>nul
set LIBRARY_DIR=%LIBRARY_DIR%
uvicorn backend.main:app --host 127.0.0.1 --port 8765
"""
    (bundle_dir / "start.sh").write_text(sh_content)
    (bundle_dir / "start.bat").write_text(bat_content)
    try:
        import os
        os.chmod(bundle_dir / "start.sh", 0o755)
    except Exception:
        pass
