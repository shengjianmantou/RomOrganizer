"""
Import orchestrator — scans source dirs, identifies ROMs, copies to library,
fetches metadata, stores in DB. Streams progress via an async queue.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.database import get_session
from backend.db.models import Game, ImportJob, RomFile, System
from backend.services import dat_matcher, filename_parser, hasher, scraper, scanner

log = logging.getLogger(__name__)

# In-memory progress queues keyed by job_id
_progress_queues: dict[int, asyncio.Queue] = {}


def get_progress_queue(job_id: int) -> asyncio.Queue:
    if job_id not in _progress_queues:
        _progress_queues[job_id] = asyncio.Queue()
    return _progress_queues[job_id]


async def stream_progress(job_id: int) -> AsyncIterator[dict]:
    """Yield progress events for an import job (used by SSE endpoint)."""
    q = get_progress_queue(job_id)
    while True:
        event = await q.get()
        yield event
        if event.get("status") in ("done", "error"):
            break


async def start_import(job_id: int, source_directories: list[str]) -> None:
    """Main import coroutine — runs in background."""
    q = get_progress_queue(job_id)

    def emit(event: dict):
        asyncio.get_event_loop().call_soon_threadsafe(q.put_nowait, event)

    with get_session() as session:
        job = session.get(ImportJob, job_id)
        if not job:
            return
        job.status = "running"
        session.commit()

    try:
        # Load DAT files
        dat_count = dat_matcher.load_all_dats()
        emit({"type": "info", "message": f"Loaded {dat_count} DAT entries"})

        # Build system lookup: esde_folder -> System
        with get_session() as session:
            systems_by_folder = {s.esde_folder: s for s in session.query(System).all()}
            systems_by_ext: dict[str, list[System]] = {}
            for s in systems_by_folder.values():
                for ext in s.extension_list:
                    systems_by_ext.setdefault(ext, []).append(s)

        esde_folders = set(systems_by_folder.keys())

        # Count total files first
        total = 0
        for src in source_directories:
            total += scanner.count_rom_files(Path(src))

        with get_session() as session:
            job = session.get(ImportJob, job_id)
            job.total_files = total
            session.commit()

        emit({"type": "total", "total": total})

        processed = imported = skipped = errors = 0

        for src_dir_str in source_directories:
            src_dir = Path(src_dir_str)
            async for rom_path in scanner.scan_directory(src_dir):
                try:
                    result = await _process_rom(
                        rom_path, src_dir, systems_by_folder, systems_by_ext, esde_folders
                    )
                    if result == "imported":
                        imported += 1
                    elif result == "skipped":
                        skipped += 1
                    elif result == "error":
                        errors += 1
                except Exception as e:
                    log.exception(f"Unhandled error processing {rom_path}: {e}")
                    errors += 1

                processed += 1
                if processed % 10 == 0 or processed == total:
                    with get_session() as session:
                        job = session.get(ImportJob, job_id)
                        job.processed_files = processed
                        job.imported_games = imported
                        job.skipped_duplicates = skipped
                        job.errors = errors
                        session.commit()
                    emit({
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "imported": imported,
                        "skipped": skipped,
                        "errors": errors,
                    })

        with get_session() as session:
            job = session.get(ImportJob, job_id)
            job.status = "done"
            job.finished_at = datetime.now(timezone.utc)
            job.processed_files = processed
            job.imported_games = imported
            job.skipped_duplicates = skipped
            job.errors = errors
            session.commit()

        emit({"type": "done", "status": "done", "imported": imported, "skipped": skipped, "errors": errors})

    except Exception as e:
        log.exception(f"Import job {job_id} failed: {e}")
        with get_session() as session:
            job = session.get(ImportJob, job_id)
            job.status = "error"
            job.finished_at = datetime.now(timezone.utc)
            job.log = str(e)
            session.commit()
        emit({"type": "error", "status": "error", "message": str(e)})
    finally:
        # Clean up queue after a delay
        await asyncio.sleep(60)
        _progress_queues.pop(job_id, None)


async def _process_rom(
    rom_path: Path,
    src_dir: Path,
    systems_by_folder: dict[str, System],
    systems_by_ext: dict[str, list[System]],
    esde_folders: set[str],
) -> str:
    """Process a single ROM file. Returns 'imported', 'skipped', or 'error'."""
    try:
        # 1. Compute hashes
        loop = asyncio.get_event_loop()
        hashes = await loop.run_in_executor(None, hasher.compute_hashes, rom_path)

        # 2. Check for DAT lookup (with header-aware matching)
        dat_entry = dat_matcher.lookup(
            crc32=hashes.crc32, md5=hashes.md5, sha1=hashes.sha1, hashes=hashes
        )

        # 3. Absolute dedup check — if already in library, update metadata if new DAT match found
        if dat_matcher.is_duplicate_hash(
            crc32=hashes.crc32, md5=hashes.md5, sha1=hashes.sha1
        ):
            if dat_entry:
                from backend.db.models import RomFile
                with get_session() as session:
                    rf = (
                        session.query(RomFile)
                        .filter(
                            (RomFile.sha1 == (hashes.sha1 or "").lower())
                            | (RomFile.md5 == (hashes.md5 or "").lower())
                            | (RomFile.crc32 == (hashes.crc32 or "").lower().zfill(8))
                        )
                        .first()
                    )
                    if rf and rf.game:
                        rf.game.title = dat_entry.name
                        rf.game.sort_title = _make_sort_title(dat_entry.name)
                        rf.game.no_intro_name = dat_entry.name
                        rf.game.region = dat_entry.region
                        if dat_entry.languages:
                            rf.game.languages = ",".join(dat_entry.languages)
                        rf.dat_matched = True
                        session.commit()
            return "skipped"

        # 4. Filename parse (always done for fallback)
        parsed = filename_parser.parse_rom_filename(rom_path.name)

        # 5. Determine system
        system = _resolve_system(
            rom_path, src_dir, dat_entry, systems_by_folder, systems_by_ext, esde_folders
        )
        if not system:
            log.debug(f"Could not resolve system for {rom_path.name}, skipping")
            return "error"

        # 6. Determine canonical title
        if dat_entry:
            title = dat_entry.name
            region = dat_entry.region
            languages = dat_entry.languages
            dat_matched = True
            no_intro_name = dat_entry.name
        else:
            title = parsed.clean_title or rom_path.stem
            region = parsed.region
            languages = parsed.languages
            dat_matched = False
            no_intro_name = None

        # 7. Copy ROM to library
        dest_dir = settings.files_dir / system.esde_folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / rom_path.name
        if not dest_path.exists():
            await loop.run_in_executor(None, shutil.copy2, str(rom_path), str(dest_path))

        # 8. Create DB record
        with get_session() as session:
            game = Game(
                title=title,
                sort_title=_make_sort_title(title),
                system_id=system.id,
                region=region,
                languages=",".join(languages) if languages else None,
                no_intro_name=no_intro_name,
            )
            session.add(game)
            session.flush()

            rom_file = RomFile(
                game_id=game.id,
                library_path=str(dest_path.relative_to(settings.library_dir)),
                original_filename=rom_path.name,
                file_format=rom_path.suffix.lower().lstrip("."),
                crc32=hashes.crc32,
                md5=hashes.md5,
                sha1=hashes.sha1,
                file_size=hashes.file_size,
                dat_matched=dat_matched,
            )
            session.add(rom_file)
            game_id = game.id
            session.commit()

        # 9. Fetch metadata asynchronously
        if settings.scrape_on_import:
            asyncio.ensure_future(
                _scrape_and_update(
                    game_id=game_id,
                    title=title,
                    system=system,
                    hashes=hashes,
                    filename=rom_path.name,
                )
            )

        return "imported"

    except Exception as e:
        log.warning(f"Error processing {rom_path}: {e}")
        return "error"


async def _scrape_and_update(
    game_id: int,
    title: str,
    system: System,
    hashes: hasher.RomHashes,
    filename: str,
) -> None:
    """Fetch online metadata and update the game record."""
    try:
        meta = await scraper.fetch_metadata(
            title=title,
            system_screenscraper_id=system.screenscraper_id,
            system_thegamesdb_id=system.thegamesdb_id,
            crc32=hashes.crc32,
            md5=hashes.md5,
            sha1=hashes.sha1,
            filename=filename,
        )
        if not meta:
            return

        # Download cover art
        cover_path = None
        if meta.cover_art_url:
            ext = Path(meta.cover_art_url).suffix or ".jpg"
            cover_dest = settings.media_dir / "covers" / f"{game_id}{ext}"
            if await scraper.download_image(meta.cover_art_url, cover_dest):
                cover_path = str(cover_dest.relative_to(settings.library_dir))

        # Download screenshot
        screenshot_path = None
        if meta.screenshot_url:
            ext = Path(meta.screenshot_url).suffix or ".jpg"
            shot_dest = settings.media_dir / "screenshots" / f"{game_id}{ext}"
            if await scraper.download_image(meta.screenshot_url, shot_dest):
                screenshot_path = str(shot_dest.relative_to(settings.library_dir))

        with get_session() as session:
            game = session.get(Game, game_id)
            if not game:
                return
            if meta.title:
                game.title = meta.title
                game.sort_title = _make_sort_title(meta.title)
            if meta.description:
                game.description = meta.description
            if meta.genre:
                game.genre = meta.genre
            if meta.publisher:
                game.publisher = meta.publisher
            if meta.developer:
                game.developer = meta.developer
            if meta.release_year:
                game.release_year = meta.release_year
            if meta.rating is not None:
                game.rating = meta.rating
            if meta.players:
                game.players = meta.players
            if meta.series:
                game.series = meta.series
            if meta.screenscraper_id:
                game.screenscraper_id = meta.screenscraper_id
            if cover_path:
                game.cover_art_path = cover_path
            if screenshot_path:
                game.screenshot_path = screenshot_path
            session.commit()

    except Exception as e:
        log.debug(f"Scrape failed for game {game_id}: {e}")


def _resolve_system(
    rom_path: Path,
    src_dir: Path,
    dat_entry,
    systems_by_folder: dict[str, System],
    systems_by_ext: dict[str, list[System]],
    esde_folders: set[str],
) -> System | None:
    # 1. From DAT entry system name
    if dat_entry and dat_entry.system_name:
        for s in systems_by_folder.values():
            if s.name.lower() in dat_entry.system_name.lower() or s.esde_folder in dat_entry.system_name.lower():
                return s

    # 2. From parent directory / path parts matching an ES-DE folder
    inferred = scanner.infer_system_from_directory(rom_path, esde_folders)
    if inferred and inferred in systems_by_folder:
        return systems_by_folder[inferred]

    # 3. If archive (.zip, .7z, .rar): inspect extension of ROM file inside archive
    internal_ext = scanner.detect_internal_extension(rom_path)
    if internal_ext and internal_ext in systems_by_ext:
        candidates = systems_by_ext[internal_ext]
        if len(candidates) == 1:
            return candidates[0]
        # If multiple (e.g. ngp vs ngpc), prefer ngpc or inferred
        for c in candidates:
            if c.esde_folder == "ngpc":
                return c
        return candidates[0]

    # 4. From file extension directly
    ext = rom_path.suffix.lower()
    candidates = systems_by_ext.get(ext, [])
    if len(candidates) == 1:
        return candidates[0]

    # 5. Ambiguous: take first candidate
    if candidates:
        return candidates[0]

    return None


def _make_sort_title(title: str) -> str:
    """Create a sort-friendly version of a title (move leading 'The', 'A', 'An')."""
    for article in ("The ", "A ", "An "):
        if title.startswith(article):
            return title[len(article):] + f", {article.strip()}"
    return title
