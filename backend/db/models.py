"""SQLAlchemy ORM models."""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class System(Base):
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    esde_folder: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    extensions: Mapped[str] = mapped_column(String(512), nullable=False)  # comma-separated
    manufacturer: Mapped[Optional[str]] = mapped_column(String(128))
    release_year: Mapped[Optional[int]] = mapped_column(Integer)
    screenscraper_id: Mapped[Optional[int]] = mapped_column(Integer)
    thegamesdb_id: Mapped[Optional[int]] = mapped_column(Integer)

    games: Mapped[list[Game]] = relationship("Game", back_populates="system")

    @property
    def extension_list(self) -> list[str]:
        return [e.strip() for e in self.extensions.split(",")]


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    sort_title: Mapped[Optional[str]] = mapped_column(String(512), index=True)
    system_id: Mapped[int] = mapped_column(Integer, ForeignKey("systems.id"), nullable=False, index=True)
    region: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    languages: Mapped[Optional[str]] = mapped_column(String(256), index=True)  # comma-sep: En,Zh,Ja
    series: Mapped[Optional[str]] = mapped_column(String(256), index=True)
    genre: Mapped[Optional[str]] = mapped_column(String(256))
    publisher: Mapped[Optional[str]] = mapped_column(String(256))
    developer: Mapped[Optional[str]] = mapped_column(String(256))
    release_year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    cover_art_path: Mapped[Optional[str]] = mapped_column(String(512))
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(512))
    no_intro_name: Mapped[Optional[str]] = mapped_column(String(512))
    screenscraper_id: Mapped[Optional[int]] = mapped_column(Integer)
    rating: Mapped[Optional[float]] = mapped_column(Float)
    players: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    system: Mapped[System] = relationship("System", back_populates="games")
    rom_files: Mapped[list[RomFile]] = relationship("RomFile", back_populates="game", cascade="all, delete-orphan")


class RomFile(Base):
    __tablename__ = "rom_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    library_path: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_format: Mapped[str] = mapped_column(String(16), nullable=False)  # raw, zip, 7z, rar
    crc32: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    md5: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    sha1: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    dat_matched: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    game: Mapped[Game] = relationship("Game", back_populates="rom_files")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_directories: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, running, done, error
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    imported_games: Mapped[int] = mapped_column(Integer, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_ids: Mapped[str] = mapped_column(Text, nullable=False)  # JSON list of game IDs
    export_dir: Mapped[str] = mapped_column(String(1024), nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), default="uncompressed")  # uncompressed, original, zip, 7z
    dedup_mode: Mapped[str] = mapped_column(String(32), default="single")  # single, all
    lang_priority: Mapped[str] = mapped_column(String(64), default="En,Zh,Ja")  # comma-sep ordered list
    rename_files: Mapped[bool] = mapped_column(Boolean, default=True)
    only_preferred_languages: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_games: Mapped[int] = mapped_column(Integer, default=0)
    exported_games: Mapped[int] = mapped_column(Integer, default=0)
    skipped_games: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    log: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
