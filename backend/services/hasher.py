"""
ROM hashing service — computes CRC32, MD5, SHA1 for ROM files.
Handles plain files, ZIP archives, 7z, and RAR.
Detects platform headers (iNES 16-byte, SNES 512-byte copier header, Lynx 64-byte, PCE 512-byte)
and computes both full-file and headerless checksums for 100% DAT compatibility.
"""
from __future__ import annotations

import binascii
import hashlib
import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RomHashes:
    crc32: str  # 8 hex chars
    md5: str  # 32 hex chars
    sha1: str  # 40 hex chars
    file_size: int
    headerless_crc32: Optional[str] = None
    headerless_md5: Optional[str] = None
    headerless_sha1: Optional[str] = None
    headerless_size: Optional[int] = None
    header_bytes: Optional[bytes] = None
    is_nes: bool = False
    nes_prg_count: int = 0
    nes_chr_count: int = 0
    raw_data: Optional[bytes] = None  # in-memory buffer if small enough (<= 64MB)


ROM_EXTENSIONS = {
    ".nes", ".unf", ".unif", ".sfc", ".smc", ".snes", ".bs", ".fig", ".swc",
    ".n64", ".z64", ".v64", ".gba", ".gbc", ".gb",
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


def _pick_best_rom_candidate(names: list[str]) -> str | None:
    """Pick the best ROM file among candidates (prefers [!], (USA), (World), (Europe))."""
    if not names:
        return None
    if len(names) == 1:
        return names[0]

    # Preference score: lower = better
    def score(name: str) -> tuple[int, int, int, str]:
        n = name.lower()
        verified = 0 if "[!]" in name else 1
        region_score = 10
        if "(u)" in n or "(usa)" in n:
            region_score = 1
        elif "(w)" in n or "(world)" in n:
            region_score = 2
        elif "(e)" in n or "(europe)" in n:
            region_score = 3
        elif "(j)" in n or "(japan)" in n:
            region_score = 4
        
        # Penalize bad dumps, hacks, overdumps
        penalty = 1 if any(t in n for t in ["[b", "[h", "[o", "[t", "[a", "beta", "proto"]) else 0
        return (penalty, verified, region_score, name)

    return min(names, key=score)


def compute_hashes_from_data(data: bytes) -> RomHashes:
    """Compute full and headerless hashes from raw ROM bytes."""
    full_crc = binascii.crc32(data) & 0xFFFFFFFF
    full_md5 = hashlib.md5(data).hexdigest()
    full_sha1 = hashlib.sha1(data).hexdigest()

    headerless_crc = None
    headerless_md5 = None
    headerless_sha1 = None
    headerless_size = None
    header_bytes = None
    is_nes = False
    nes_prg_count = 0
    nes_chr_count = 0

    # 1. NES (16-byte iNES / NES 2.0 header: 'NES\x1a')
    if len(data) > 16 and data[:4] == b"NES\x1a":
        is_nes = True
        header_bytes = data[:16]
        nes_prg_count = data[4]
        nes_chr_count = data[5]
        hl_data = data[16:]
        hl_crc = binascii.crc32(hl_data) & 0xFFFFFFFF
        headerless_crc = f"{hl_crc:08x}"
        headerless_md5 = hashlib.md5(hl_data).hexdigest()
        headerless_sha1 = hashlib.sha1(hl_data).hexdigest()
        headerless_size = len(hl_data)

    # 2. SNES (512-byte copier header if len % 1024 == 512)
    elif len(data) > 512 and (len(data) % 1024 == 512):
        header_bytes = data[:512]
        hl_data = data[512:]
        hl_crc = binascii.crc32(hl_data) & 0xFFFFFFFF
        headerless_crc = f"{hl_crc:08x}"
        headerless_md5 = hashlib.md5(hl_data).hexdigest()
        headerless_sha1 = hashlib.sha1(hl_data).hexdigest()
        headerless_size = len(hl_data)

    # 3. Atari Lynx (64-byte 'LYNX' header)
    elif len(data) > 64 and data[:4] == b"LYNX":
        header_bytes = data[:64]
        hl_data = data[64:]
        hl_crc = binascii.crc32(hl_data) & 0xFFFFFFFF
        headerless_crc = f"{hl_crc:08x}"
        headerless_md5 = hashlib.md5(hl_data).hexdigest()
        headerless_sha1 = hashlib.sha1(hl_data).hexdigest()
        headerless_size = len(hl_data)

    # 4. N64 byte-swapped (.v64) or little-endian (.n64) -> normalize to big-endian (.z64)
    elif len(data) >= 4 and data[:4] in (b"\x37\x80\x40\x12", b"\x40\x12\x37\x80"):
        if data[:4] == b"\x37\x80\x40\x12":  # .v64 (byteswapped 16-bit)
            ba = bytearray(data)
            ba[0::2], ba[1::2] = data[1::2], data[0::2]
            norm_data = bytes(ba)
        else:  # .n64 (little-endian 32-bit)
            ba = bytearray(data)
            ba[0::4], ba[1::4], ba[2::4], ba[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
            norm_data = bytes(ba)
        hl_crc = binascii.crc32(norm_data) & 0xFFFFFFFF
        headerless_crc = f"{hl_crc:08x}"
        headerless_md5 = hashlib.md5(norm_data).hexdigest()
        headerless_sha1 = hashlib.sha1(norm_data).hexdigest()
        headerless_size = len(norm_data)

    return RomHashes(
        crc32=f"{full_crc:08x}",
        md5=full_md5,
        sha1=full_sha1,
        file_size=len(data),
        headerless_crc32=headerless_crc,
        headerless_md5=headerless_md5,
        headerless_sha1=headerless_sha1,
        headerless_size=headerless_size,
        header_bytes=header_bytes,
        is_nes=is_nes,
        nes_prg_count=nes_prg_count,
        nes_chr_count=nes_chr_count,
        raw_data=data if len(data) <= (64 << 20) else None,
    )


def compute_hashes(path: Path) -> RomHashes:
    """
    Compute full and header-aware hashes for a ROM file.
    Inspects inside ZIP, 7z, and RAR archives.
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
    file_size = path.stat().st_size
    if file_size <= (64 << 20):
        try:
            with open(path, "rb") as f:
                data = f.read()
            return compute_hashes_from_data(data)
        except Exception:
            pass

    with open(path, "rb") as f:
        return _stream_hash_entry(f)


def _hash_zip(path: Path) -> RomHashes:
    """Extract and hash the best ROM file found inside a ZIP."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            rom_names = [n for n in names if _is_rom_file(n) and not n.endswith("/")]
            target = _pick_best_rom_candidate(rom_names) if rom_names else (names[0] if names else None)
            if target is None:
                return _hash_plain(path)
            
            info = zf.getinfo(target)
            if info.file_size <= (64 << 20):
                data = zf.read(target)
                return compute_hashes_from_data(data)
            else:
                with zf.open(target) as entry:
                    return _stream_hash_entry(entry)
    except Exception:
        return _hash_plain(path)


def _hash_7z(path: Path) -> RomHashes:
    """Extract and hash the best ROM file found inside a 7z archive."""
    import tempfile
    try:
        import py7zr
        with py7zr.SevenZipFile(path, mode="r") as szf:
            names = szf.getnames()
            rom_names = [n for n in names if _is_rom_file(n)]
            target = _pick_best_rom_candidate(rom_names) if rom_names else (names[0] if names else None)
            if target is None:
                return _hash_plain(path)
            
            with tempfile.TemporaryDirectory() as tmpdir:
                szf.extract(path=tmpdir, targets=[target])
                out_file = Path(tmpdir) / target
                if out_file.exists():
                    return _hash_plain(out_file)
        return _hash_plain(path)
    except Exception:
        return _hash_plain(path)


def _hash_rar(path: Path) -> RomHashes:
    """Extract and hash the best ROM file found inside a RAR archive."""
    import tempfile
    try:
        import rarfile
        with rarfile.RarFile(path, "r") as rf:
            names = [i.filename for i in rf.infolist() if not i.is_dir()]
            rom_names = [n for n in names if _is_rom_file(n)]
            target = _pick_best_rom_candidate(rom_names) if rom_names else (names[0] if names else None)
            if target is None:
                return _hash_plain(path)
            with tempfile.TemporaryDirectory() as tmpdir:
                rf.extract(target, tmpdir)
                out_file = Path(tmpdir) / target
                if out_file.exists():
                    return _hash_plain(out_file)
        return _hash_plain(path)
    except Exception:
        return _hash_plain(path)


def _stream_hash_entry(stream: io.IOBase) -> RomHashes:
    crc = 0
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    total = 0
    while True:
        chunk = stream.read(1 << 20)
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
