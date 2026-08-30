"""
No-Intro DAT XML matcher — loads DAT files and looks up ROM entries by hash.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from lxml import etree

from backend.config import settings


@dataclass
class DatEntry:
    name: str  # Canonical No-Intro name
    region: str
    languages: list[str]
    crc32: Optional[str] = None
    md5: Optional[str] = None
    sha1: Optional[str] = None
    system_name: Optional[str] = None  # from DAT header


# In-memory index: crc32 -> DatEntry, md5 -> DatEntry, sha1 -> DatEntry
_CRC_INDEX: dict[str, DatEntry] = {}
_MD5_INDEX: dict[str, DatEntry] = {}
_SHA1_INDEX: dict[str, DatEntry] = {}
_LOADED_DATS: set[Path] = set()

# Lazy-loaded flag
_initialized = False


_REGION_RE = re.compile(r"\(([^)]+)\)")
_LANG_PAREN_RE = re.compile(r"\(([A-Z][a-z](?:,[A-Z][a-z])*)\)")


def _parse_no_intro_region(name: str) -> str:
    """Extract the first region tag from a No-Intro name."""
    match = _REGION_RE.search(name)
    if match:
        return match.group(1)
    return ""


def _parse_no_intro_languages(name: str) -> list[str]:
    """Extract comma-separated language codes from a No-Intro name."""
    langs: list[str] = []
    for match in _LANG_PAREN_RE.finditer(name):
        parts = match.group(1).split(",")
        langs.extend(p.strip() for p in parts)
    return langs


def _load_dat_file(dat_path: Path) -> int:
    """Parse a No-Intro DAT XML and index all ROM entries. Returns count loaded."""
    count = 0
    try:
        tree = etree.parse(str(dat_path))
        root = tree.getroot()

        # Get system name from header
        header = root.find("header")
        system_name = None
        if header is not None:
            name_el = header.find("name")
            if name_el is not None and name_el.text:
                system_name = name_el.text.strip()

        for game in root.findall("game"):
            game_name = game.get("name", "")
            region = _parse_no_intro_region(game_name)
            languages = _parse_no_intro_languages(game_name)

            for rom in game.findall("rom"):
                crc = (rom.get("crc") or "").lower().zfill(8) or None
                md5 = (rom.get("md5") or "").lower() or None
                sha1 = (rom.get("sha1") or "").lower() or None

                entry = DatEntry(
                    name=game_name,
                    region=region,
                    languages=languages,
                    crc32=crc,
                    md5=md5,
                    sha1=sha1,
                    system_name=system_name,
                )

                if crc:
                    _CRC_INDEX[crc] = entry
                if md5:
                    _MD5_INDEX[md5] = entry
                if sha1:
                    _SHA1_INDEX[sha1] = entry
                count += 1
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to parse DAT {dat_path}: {e}")
    return count


def load_all_dats(dat_dir: Path | None = None) -> int:
    """Load all .dat and .xml files from the DAT directory. Returns total entries."""
    global _initialized
    dir_ = dat_dir or settings.dat_files_dir
    total = 0
    for dat_file in sorted(dir_.glob("**/*.dat")) + sorted(dir_.glob("**/*.xml")):
        if dat_file not in _LOADED_DATS:
            total += _load_dat_file(dat_file)
            _LOADED_DATS.add(dat_file)
    _initialized = True
    return total


def lookup(crc32: str | None = None, md5: str | None = None, sha1: str | None = None) -> Optional[DatEntry]:
    """
    Look up a ROM entry by hash. Tries SHA1, then MD5, then CRC32.
    Returns None if no match found.
    """
    if not _initialized:
        load_all_dats()

    if sha1:
        entry = _SHA1_INDEX.get(sha1.lower())
        if entry:
            return entry
    if md5:
        entry = _MD5_INDEX.get(md5.lower())
        if entry:
            return entry
    if crc32:
        entry = _CRC_INDEX.get(crc32.lower().zfill(8))
        if entry:
            return entry
    return None


def is_duplicate_hash(crc32: str | None = None, md5: str | None = None, sha1: str | None = None) -> bool:
    """Check if this exact hash is already indexed (used for absolute hash dedup)."""
    from backend.db.database import get_session
    from backend.db.models import RomFile
    with get_session() as session:
        q = session.query(RomFile)
        if sha1:
            q = q.filter(RomFile.sha1 == sha1.lower())
            if q.count() > 0:
                return True
        if md5:
            q2 = session.query(RomFile).filter(RomFile.md5 == md5.lower())
            if q2.count() > 0:
                return True
        if crc32:
            q3 = session.query(RomFile).filter(RomFile.crc32 == crc32.lower().zfill(8))
            if q3.count() > 0:
                return True
    return False


def get_dat_stats() -> dict:
    if not _initialized:
        load_all_dats()
    return {
        "loaded_dats": len(_LOADED_DATS),
        "crc_entries": len(_CRC_INDEX),
        "md5_entries": len(_MD5_INDEX),
        "sha1_entries": len(_SHA1_INDEX),
        "dat_files": [str(p) for p in sorted(_LOADED_DATS)],
    }
