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
        lang_priority = [l.strip() for l in job.lang_priority.split(",") if l.strip()]
        rename_files = getattr(job, "rename_files", True)
        only_preferred_languages = getattr(job, "only_preferred_languages", False)

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

        # Optional: Discard foreign games not matching preferred languages
        if only_preferred_languages:
            games_data = [
                item for item in games_data
                if _is_preferred_language(item[0], lang_priority)
            ]

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

        if only_preferred_languages:
            to_export = [item for item in to_export if _is_preferred_language(item[0], lang_priority)]

        # Gamelist data per system
        gamelists: dict[str, list[dict]] = {}

        for g, sys_, rom_files in to_export:
            try:
                if not rom_files:
                    skipped += 1
                    continue

                rom_file = rom_files[0]
                src_path = settings.library_dir / rom_file.library_path

                # Determine output path
                dest_system_dir = export_dir / "roms" / sys_.esde_folder
                dest_system_dir.mkdir(parents=True, exist_ok=True)

                custom_title = g.title if rename_files else None

                loop = asyncio.get_event_loop()
                dest_filename = await loop.run_in_executor(
                    None, _write_rom, src_path, dest_system_dir, output_format, custom_title
                )

                if dest_filename:
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


import re
import tempfile
from backend.services.hasher import ROM_EXTENSIONS, _pick_best_rom_candidate


def _sanitize_filename(name: str) -> str:
    """Sanitize title for filesystem usage."""
    s = re.sub(r'[\/\\:\*\?"<>\|]', '_', name).strip()
    return s or "game"


def _normalize_title(title: str) -> str:
    """
    Normalize title for 1G1R deduplication.
    Strips all parentheses (tags), brackets, revisions, versions, leading articles,
    and non-alphanumeric punctuation so variants like 'Dr. Mario (Europe)' and
    'Dr. Mario (Japan, USA)' produce the exact same key 'drmario'.
    """
    # Strip (tag) and [tag]
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", title)
    t = t.lower().strip()
    # Strip leading articles
    for article in ("the ", "a ", "an "):
        if t.startswith(article):
            t = t[len(article):]
    # Remove all non-alphanumeric characters
    t = re.sub(r"[^a-z0-9]", "", t)
    return t or title.lower().strip()


_PREFERRED_LANG_CODES = {"en", "eng", "zh", "zhs", "zht"}
_PREFERRED_REGIONS = {"usa", "us", "world", "europe", "eur", "uk", "australia", "canada", "china", "taiwan", "hong kong"}


def _is_preferred_language(game: Game, lang_priority: list[str] | None = None) -> bool:
    """
    Check if game is an English, World, Europe, or Chinese release.
    Excludes standalone foreign games (e.g. Japanese-only, German-only, French-only).
    """
    t_lower = game.title.lower()
    r_lower = (game.region or "").lower()
    langs = {l.strip().lower() for l in (game.languages or "").split(",") if l.strip()}

    # 1. Explicit English or Chinese language code
    if langs & _PREFERRED_LANG_CODES:
        return True

    # 2. Preferred region (USA, World, Europe, UK, Australia, Canada, China, Taiwan, Hong Kong)
    r_parts = {p.strip() for p in r_lower.split(",")}
    if r_parts & _PREFERRED_REGIONS:
        return True
    for pr in _PREFERRED_REGIONS:
        if pr in r_lower:
            return True

    # 3. Preferred region/language tag in title
    tags = re.findall(r"[\(\[](.*?)[\)\]]", t_lower)
    for tag in tags:
        for p in [p.strip() for p in tag.split(",")]:
            if p in ["usa", "u", "ju", "world", "w", "europe", "e", "eur", "uk", "china", "taiwan", "hong kong", "zh", "zhs", "zht", "en", "eng"]:
                return True

    return False


def _pick_best_version(
    group: list[tuple[Game, System, list[RomFile]]],
    lang_priority: list[str],
) -> tuple[Game, System, list[RomFile]]:
    """
    From a group of same-title games (variants), pick the best single version.
    Priority order:
      1. Retail release over Beta / Proto / Demo / Hack / Bad dump
      2. USA / North America / En
      3. World / En
      4. Europe / UK / En
      5. Chinese (China / Taiwan / Hong Kong / Zh)
      6. Custom language priority from settings
      7. Other foreign languages
      8. Higher revision over base release (Rev 1 > Rev 0)
    """
    def score(item: tuple[Game, System, list[RomFile]]) -> tuple[int, float, int]:
        g, _, _ = item
        t_lower = g.title.lower()
        r_lower = (g.region or "").lower()
        langs = [l.strip().lower() for l in (g.languages or "").split(",") if l.strip()]

        # 1. Beta / Demo / Proto / Hack penalty
        is_special = any(
            w in t_lower
            for w in ["beta", "proto", "sample", "demo", "hack", "unl", "bad", "[b", "[h", "[t", "[o"]
        )
        special_penalty = 100 if is_special else 0

        # 2. Region / Language Rank
        if "usa" in r_lower or "(usa)" in t_lower or "(u)" in t_lower or "(ju)" in t_lower:
            rank = 1.0  # USA
        elif "world" in r_lower or "(world)" in t_lower or "(w)" in t_lower:
            rank = 2.0  # World
        elif "europe" in r_lower or "(europe)" in t_lower or "(e)" in t_lower or "(eur)" in t_lower or "uk" in r_lower:
            rank = 3.0  # Europe
        elif any(z in r_lower for z in ["china", "taiwan", "hong kong"]) or any(z in langs for z in ["zh", "zhs", "zht"]):
            rank = 4.0  # Chinese
        elif "en" in langs or "eng" in langs:
            rank = 3.5  # Other English
        else:
            # Check user custom priority
            parsed = parse_rom_filename(g.title)
            parsed.languages = langs or parsed.languages
            user_score = parsed.lang_priority_score(lang_priority)
            rank = 10.0 + user_score

        # 3. Revision score (higher revision -> lower negative score for min())
        rev_match = re.search(r"rev\s*([a-z0-9]+)", t_lower)
        rev_score = 0
        if rev_match:
            val = rev_match.group(1)
            rev_score = -int(val) if val.isdigit() else -(ord(val[0]) - ord('a') + 1)

        return (special_penalty, rank, rev_score)

    return min(group, key=score)


def _extract_uncompressed_rom(src_path: Path, dest_dir: Path, custom_stem: str | None = None) -> str | None:
    """Extract raw uncompressed ROM from an archive or copy raw ROM file directly."""
    ext = src_path.suffix.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)

    if ext == ".zip":
        try:
            with zipfile.ZipFile(src_path, "r") as zf:
                rom_names = [n for n in zf.namelist() if Path(n).suffix.lower() in ROM_EXTENSIONS and not n.endswith("/")]
                target = _pick_best_rom_candidate(rom_names) if rom_names else (zf.namelist()[0] if zf.namelist() else None)
                if not target:
                    return None
                rom_ext = Path(target).suffix
                out_name = f"{custom_stem}{rom_ext}" if custom_stem else Path(target).name
                dest_file = dest_dir / out_name
                with zf.open(target) as entry, open(dest_file, "wb") as out_f:
                    shutil.copyfileobj(entry, out_f)
                return out_name
        except Exception as e:
            log.warning(f"Failed to uncompress zip {src_path}: {e}")
            return None

    elif ext == ".7z":
        try:
            import py7zr
            with py7zr.SevenZipFile(src_path, "r") as szf:
                rom_names = [n for n in szf.getnames() if Path(n).suffix.lower() in ROM_EXTENSIONS]
                target = _pick_best_rom_candidate(rom_names) if rom_names else (szf.getnames()[0] if szf.getnames() else None)
                if not target:
                    return None
                with tempfile.TemporaryDirectory() as tmpdir:
                    szf.extract(path=tmpdir, targets=[target])
                    temp_file = Path(tmpdir) / target
                    rom_ext = temp_file.suffix
                    out_name = f"{custom_stem}{rom_ext}" if custom_stem else temp_file.name
                    dest_file = dest_dir / out_name
                    shutil.copy2(str(temp_file), str(dest_file))
                    return out_name
        except Exception as e:
            log.warning(f"Failed to uncompress 7z {src_path}: {e}")
            return None

    elif ext == ".rar":
        try:
            import rarfile
            with rarfile.RarFile(src_path, "r") as rf:
                rom_names = [i.filename for i in rf.infolist() if not i.isdir() and Path(i.filename).suffix.lower() in ROM_EXTENSIONS]
                target = _pick_best_rom_candidate(rom_names) if rom_names else (rf.infolist()[0].filename if rf.infolist() else None)
                if not target:
                    return None
                rom_ext = Path(target).suffix
                out_name = f"{custom_stem}{rom_ext}" if custom_stem else Path(target).name
                dest_file = dest_dir / out_name
                with rf.open(target) as entry, open(dest_file, "wb") as out_f:
                    shutil.copyfileobj(entry, out_f)
                return out_name
        except Exception as e:
            log.warning(f"Failed to uncompress rar {src_path}: {e}")
            return None

    else:
        # Already an uncompressed raw ROM file
        rom_ext = src_path.suffix
        out_name = f"{custom_stem}{rom_ext}" if custom_stem else src_path.name
        dest_file = dest_dir / out_name
        shutil.copy2(str(src_path), str(dest_file))
        return out_name


def _write_rom(
    src_path: Path,
    dest_dir: Path,
    output_format: str,
    custom_title: str | None = None,
) -> str | None:
    """Write a ROM to dest_dir in the desired format, optionally renaming it."""
    try:
        stem = _sanitize_filename(custom_title) if custom_title else src_path.stem

        if output_format == "uncompressed":
            return _extract_uncompressed_rom(src_path, dest_dir, custom_stem=stem if custom_title else None)

        elif output_format == "zip":
            dest_name = stem + ".zip"
            dest = dest_dir / dest_name
            _compress_to_zip(src_path, dest)
            return dest_name

        elif output_format == "7z":
            dest_name = stem + ".7z"
            dest = dest_dir / dest_name
            _compress_to_7z(src_path, dest)
            return dest_name

        else:
            # Original format: keep original extension
            dest_name = f"{stem}{src_path.suffix}" if custom_title else src_path.name
            dest = dest_dir / dest_name
            shutil.copy2(str(src_path), str(dest))
            return dest_name

    except Exception as e:
        log.warning(f"Failed to write ROM {src_path}: {e}")
        return None


def _compress_to_zip(src: Path, dest: Path) -> None:
    """Compress src ROM file into a ZIP archive."""
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
