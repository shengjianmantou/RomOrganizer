"""
ROM hashing service — computes CRC32, MD5, SHA1 for ROM files.
Handles plain files, ZIP archives (reads first ROM inside), 7z, and RAR.
"""
from __future__ import annotations

import hashlib
import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RomHashes:
    crc32: str  # 8 hex chars
    md5: str  # 32 hex chars
    sha1: str  # 40 hex chars
    file_size: int


def _compute_from_data(data: bytes) -> RomHashes:
    crc = 0
    # Use binascii for CRC32 (unsigned)
    import binascii
    crc = binascii.crc32(data) & 0xFFFFFFFF
    return RomHashes(
        crc32=f"{crc:08x}",
        md5=hashlib.md5(data).hexdigest(),
        sha1=hashlib.sha1(data).hexdigest(),
        file_size=len(data),
    )


def _hash_stream(stream: io.IOBase, chunk_size: int = 1 << 20) -> RomHashes:
    """Compute hashes from a readable stream without loading all into memory."""
    import binascii
    crc = 0
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    total = 0
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        crc = binascii.crc32(chunk, crc) & 0xFFFFFFFF
        md5.update(chunk)
        sha1.update(chunk)
        total += len(chunk)
    return RomHashes(
        crc32=f"{crc:08x}",
        md5=md5.hexdigest(),
        sha1=sha1.hexdigest(),
        file_size=total,
    )


ROM_EXTENSIONS = {
    ".nes", ".sfc", ".smc", ".n64", ".z64", ".v64", ".gba", ".gbc", ".gb",
    ".nds", ".3ds", ".cia", ".nsp", ".xci",
    ".iso", ".bin", ".cue", ".chd", ".img", ".mdf",
    ".pce", ".sms", ".md", ".smd", ".gen",
    ".gg", ".ws", ".wsc", ".ngp", ".ngc",
    ".a26", ".a52", ".a78",
    ".vb", ".lnx", ".j64", ".jag",
    ".pbp", ".elf",
    ".gcm", ".gcz", ".rvz",
    ".wbfs", ".wad",
    ".vpk", ".pkg",
    ".32x",
}


def _is_rom_file(name: str) -> bool:
    return Path(name).suffix.lower() in ROM_EXTENSIONS


def compute_hashes(path: Path) -> RomHashes:
    """
    Compute CRC32/MD5/SHA1 for a ROM file.
    - If plain file: hash file content directly.
    - If ZIP: hash the first ROM entry found inside.
    - If 7z: hash the first ROM entry found inside.
    - If RAR: hash the first ROM entry found inside.
    """
    suffix = path.suffix.lower()

    if suffix == ".zip":
        return _hash_zip(path)
    elif suffix == ".7z":
        return _hash_7z(path)
    elif suffix == ".rar":
        return _hash_rar(path)
    else:
        return _hash_plain(path)


def _hash_plain(path: Path) -> RomHashes:
    with open(path, "rb") as f:
        return _hash_stream(f)


def _hash_zip(path: Path) -> RomHashes:
    """Hash the first ROM file found inside a ZIP."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            # Prefer a ROM file inside; fall back to first file
            names = zf.namelist()
            rom_names = [n for n in names if _is_rom_file(n) and not n.endswith("/")]
            target = rom_names[0] if rom_names else names[0]
            with zf.open(target) as entry:
                return _hash_stream(entry)
    except (zipfile.BadZipFile, IndexError, KeyError):
        # Fallback: hash the zip itself
        return _hash_plain(path)


def _hash_7z(path: Path) -> RomHashes:
    """Hash the first ROM file found inside a 7z archive."""
    try:
        import py7zr
        with py7zr.SevenZipFile(path, mode="r") as szf:
            names = szf.getnames()
            rom_names = [n for n in names if _is_rom_file(n)]
            target = rom_names[0] if rom_names else (names[0] if names else None)
            if target is None:
                return _hash_plain(path)
            all_data = szf.read([target])
            data = all_data[target].read()
            return _compute_from_data(data)
    except Exception:
        return _hash_plain(path)


def _hash_rar(path: Path) -> RomHashes:
    """Hash the first ROM file found inside a RAR archive."""
    try:
        import rarfile
        with rarfile.RarFile(path, "r") as rf:
            names = [i.filename for i in rf.infolist() if not i.is_dir()]
            rom_names = [n for n in names if _is_rom_file(n)]
            target = rom_names[0] if rom_names else (names[0] if names else None)
            if target is None:
                return _hash_plain(path)
            with rf.open(target) as entry:
                return _hash_stream(entry)
    except Exception:
        return _hash_plain(path)


def compute_hashes_async(path: Path):
    """Synchronous wrapper for use in thread pool executors."""
    return compute_hashes(path)
