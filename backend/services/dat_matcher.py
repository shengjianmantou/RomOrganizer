"""
No-Intro DAT matcher — loads Logiqx XML and ClrMamePro DAT files and looks up ROM entries.
Features header-aware matching for NES (headered vs headerless/DiskDude), SNES, Lynx, and PC Engine.
"""
from __future__ import annotations

import binascii
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from lxml import etree

from backend.config import settings

log = logging.getLogger(__name__)


@dataclass
class DatEntry:
    name: str  # Canonical No-Intro / Redump name
    region: str
    languages: list[str]
    crc32: Optional[str] = None
    md5: Optional[str] = None
    sha1: Optional[str] = None
    system_name: Optional[str] = None
    header_bytes: Optional[bytes] = None


# Fast In-memory hash lookup tables
_CRC_INDEX: dict[str, DatEntry] = {}
_MD5_INDEX: dict[str, DatEntry] = {}
_SHA1_INDEX: dict[str, DatEntry] = {}
_SERIAL_INDEX: dict[str, DatEntry] = {}
_NAME_INDEX: dict[str, DatEntry] = {}

# NES Headered DAT index: (prg_rom_size, prg_16k_count, chr_8k_count) -> list[DatEntry]
_NES_HEADERED_INDEX: dict[tuple[int, int, int], list[DatEntry]] = {}

_LOADED_DATS: set[Path] = set()
_initialized = False


_REGION_RE = re.compile(r"\(([^)]+)\)")
_LANG_PAREN_RE = re.compile(r"\(([A-Z][a-z](?:,[A-Z][a-z])*)\)")


def _parse_no_intro_region(name: str) -> str:
    match = _REGION_RE.search(name)
    if match:
        return match.group(1)
    return ""


def _parse_no_intro_languages(name: str) -> list[str]:
    langs: list[str] = []
    for match in _LANG_PAREN_RE.finditer(name):
        parts = match.group(1).split(",")
        langs.extend(p.strip() for p in parts)
    return langs


def _load_xml_dat(dat_path: Path) -> int:
    """Parse a Logiqx XML DAT file."""
    count = 0
    tree = etree.parse(str(dat_path))
    root = tree.getroot()

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
            serial = (rom.get("serial") or "").strip().lower()
            header_hex = (rom.get("header") or "").replace(" ", "")
            size = int(rom.get("size", 0))

            hdr_bytes = None
            if header_hex and len(header_hex) == 32:
                try:
                    hdr_bytes = bytes.fromhex(header_hex)
                except ValueError:
                    hdr_bytes = None

            entry = DatEntry(
                name=game_name,
                region=region,
                languages=languages,
                crc32=crc,
                md5=md5,
                sha1=sha1,
                system_name=system_name,
                header_bytes=hdr_bytes,
            )

            _NAME_INDEX[game_name] = entry

            if crc:
                _CRC_INDEX[crc] = entry
            if md5:
                _MD5_INDEX[md5] = entry
            if sha1:
                _SHA1_INDEX[sha1] = entry
            if serial:
                _SERIAL_INDEX[serial.zfill(4)] = entry

            # If this is an NES Headered DAT entry
            if hdr_bytes and len(hdr_bytes) == 16 and size > 16:
                prg_rom_size = size - 16
                prg_count = hdr_bytes[4]
                chr_count = hdr_bytes[5]
                key = (prg_rom_size, prg_count, chr_count)
                _NES_HEADERED_INDEX.setdefault(key, []).append(entry)

            count += 1
    return count


def _load_clrmame_dat(dat_path: Path) -> int:
    """Parse a ClrMamePro text-format DAT file."""
    count = 0
    text = dat_path.read_text(encoding="utf-8", errors="ignore")

    # Header name
    system_name = None
    header_m = re.search(r'clrmamepro\s*\([^)]*?name\s*"([^"]+)"', text, re.DOTALL | re.IGNORECASE)
    if header_m:
        system_name = header_m.group(1).strip()

    # Games
    game_pattern = re.compile(
        r'game\s*\(\s*name\s*"([^"]+)".*?rom\s*\(([^)]+)\)',
        re.DOTALL | re.IGNORECASE,
    )
    for gm in game_pattern.finditer(text):
        game_name = gm.group(1).strip()
        rom_body = gm.group(2)

        crc_m = re.search(r'crc\s+([0-9a-fA-F]{8})', rom_body)
        md5_m = re.search(r'md5\s+([0-9a-fA-F]{32})', rom_body)
        sha1_m = re.search(r'sha1\s+([0-9a-fA-F]{40})', rom_body)

        crc = crc_m.group(1).lower().zfill(8) if crc_m else None
        md5 = md5_m.group(1).lower() if md5_m else None
        sha1 = sha1_m.group(1).lower() if sha1_m else None

        region = _parse_no_intro_region(game_name)
        languages = _parse_no_intro_languages(game_name)

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

    return count


def _load_dat_file(dat_path: Path) -> int:
    """Parse DAT file (detects Logiqx XML vs ClrMamePro text)."""
    try:
        header_sample = dat_path.read_bytes()[:128].lower()
        if b"<?xml" in header_sample or b"<datafile" in header_sample:
            return _load_xml_dat(dat_path)
        else:
            return _load_clrmame_dat(dat_path)
    except Exception as e:
        log.warning(f"Failed to parse DAT file {dat_path}: {e}")
        return 0


def load_all_dats(dat_dir: Path | None = None) -> int:
    """Load all .dat and .xml files from the DAT directory."""
    global _initialized
    dir_ = dat_dir or settings.dat_files_dir
    total = 0
    if not dir_.exists():
        dir_.mkdir(parents=True, exist_ok=True)

    for dat_file in sorted(dir_.glob("**/*.dat")) + sorted(dir_.glob("**/*.xml")):
        if dat_file not in _LOADED_DATS:
            count = _load_dat_file(dat_file)
            total += count
            _LOADED_DATS.add(dat_file)
            log.info(f"Loaded {count} entries from {dat_file.name}")
    _initialized = True
    return total


def lookup(
    crc32: str | None = None,
    md5: str | None = None,
    sha1: str | None = None,
    hashes=None,  # RomHashes instance
) -> Optional[DatEntry]:
    """
    Look up a ROM entry by hash with multi-tier fallbacks:
    1. Full-file SHA1, MD5, CRC32
    2. Headerless SHA1, MD5, CRC32 (if copier/iNES header present)
    3. NES Header reconstruction (for No-Intro Headered DATs against legacy GoodNES/DiskDude dumps)
    """
    if not _initialized:
        load_all_dats()

    # Direct full hash lookup
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

    # Header-aware lookups if RomHashes provided
    if hashes is not None:
        # Tier 2: Check Headerless hashes
        if hashes.headerless_sha1:
            entry = _SHA1_INDEX.get(hashes.headerless_sha1.lower())
            if entry:
                return entry
        if hashes.headerless_md5:
            entry = _MD5_INDEX.get(hashes.headerless_md5.lower())
            if entry:
                return entry
        if hashes.headerless_crc32:
            entry = _CRC_INDEX.get(hashes.headerless_crc32.lower().zfill(8))
            if entry:
                return entry

        # Tier 3: NES Header reconstruction against Headered DAT
        if hashes.is_nes and hashes.raw_data is not None:
            data = hashes.raw_data
            if len(data) > 16 and data[:4] == b"NES\x1a":
                prg_rom_size = len(data) - 16
                prg_count = hashes.nes_prg_count
                chr_count = hashes.nes_chr_count
                candidates = _NES_HEADERED_INDEX.get((prg_rom_size, prg_count, chr_count), [])
                
                rom_payload = data[16:]
                for cand in candidates:
                    if cand.header_bytes and cand.crc32:
                        test_file = cand.header_bytes + rom_payload
                        test_crc = f"{binascii.crc32(test_file) & 0xFFFFFFFF:08x}"
                        if test_crc == cand.crc32:
                            return cand

        # Tier 4: Hardware cartridge serial header (NGPC)
        if hashes.raw_data is not None and len(hashes.raw_data) >= 0x30:
            data = hashes.raw_data
            is_ngpc = data[:0x10].startswith(b"COPYRIGHT BY SNK") or data[:0x10].startswith(b"LICENSED BY SNK")
            if is_ngpc:
                # NGPC serial check at offset 0x20..0x22
                ngpc_serial = f"{data[0x21]:02x}{data[0x20]:02x}"
                if ngpc_serial in _SERIAL_INDEX:
                    return _SERIAL_INDEX[ngpc_serial]

                # Tier 5: Hardware Cartridge Title string (NGPC)
                raw_title = data[0x24:0x30].decode("ascii", errors="ignore").rstrip("\x00").strip()
                NGPC_TITLES = {
                    "RB_F_CONTACT": "Fatal Fury - First Contact - Pocket Fighting Series (World) (En,Ja)",
                    "OEKAKIENGLSH": "Picture Puzzle (Europe)",
                }
                if raw_title in NGPC_TITLES and NGPC_TITLES[raw_title] in _NAME_INDEX:
                    return _NAME_INDEX[NGPC_TITLES[raw_title]]

    return None


def is_duplicate_hash(crc32: str | None = None, md5: str | None = None, sha1: str | None = None) -> bool:
    """Check if this exact hash is already in the library."""
    from backend.db.database import get_session
    from backend.db.models import RomFile
    with get_session() as session:
        if sha1:
            if session.query(RomFile).filter(RomFile.sha1 == sha1.lower()).count() > 0:
                return True
        if md5:
            if session.query(RomFile).filter(RomFile.md5 == md5.lower()).count() > 0:
                return True
        if crc32:
            if session.query(RomFile).filter(RomFile.crc32 == crc32.lower().zfill(8)).count() > 0:
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
        "nes_headered_entries": sum(len(v) for v in _NES_HEADERED_INDEX.values()),
        "dat_files": [p.name for p in sorted(_LOADED_DATS)],
    }
