"""Library router — browse, filter, and paginate games."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Game, RomFile, System

router = APIRouter(prefix="/api/library", tags=["library"])


class RomFileOut(BaseModel):
    id: int
    library_path: str
    original_filename: str
    file_format: str
    crc32: Optional[str] = None
    md5: Optional[str] = None
    sha1: Optional[str] = None
    file_size: Optional[int] = None
    dat_matched: bool

    class Config:
        from_attributes = True


class GameOut(BaseModel):
    id: int
    title: str
    sort_title: Optional[str] = None
    system_id: int
    system_name: str
    system_esde_folder: str
    region: Optional[str] = None
    languages: Optional[str] = None
    series: Optional[str] = None
    genre: Optional[str] = None
    publisher: Optional[str] = None
    developer: Optional[str] = None
    release_year: Optional[int] = None
    description: Optional[str] = None
    cover_art_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    no_intro_name: Optional[str] = None
    rating: Optional[float] = None
    players: Optional[int] = None
    rom_files: list[RomFileOut] = []

    class Config:
        from_attributes = True


class GamesResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[GameOut]


@router.get("/games", response_model=GamesResponse)
def list_games(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    system_ids: Optional[str] = None,  # comma-separated
    languages: Optional[str] = None,   # comma-separated, e.g. "En,Zh"
    regions: Optional[str] = None,
    genres: Optional[str] = None,
    series: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    sort_by: str = Query("sort_title", enum=["sort_title", "title", "release_year", "system_id"]),
    sort_dir: str = Query("asc", enum=["asc", "desc"]),
):
    q = db.query(Game).join(System)

    if search:
        q = q.filter(Game.title.ilike(f"%{search}%"))

    if system_ids:
        ids = [int(x) for x in system_ids.split(",") if x.strip().isdigit()]
        if ids:
            q = q.filter(Game.system_id.in_(ids))

    if languages:
        lang_list = [l.strip() for l in languages.split(",") if l.strip()]
        conditions = [Game.languages.ilike(f"%{lang}%") for lang in lang_list]
        q = q.filter(or_(*conditions))

    if regions:
        region_list = [r.strip() for r in regions.split(",") if r.strip()]
        q = q.filter(Game.region.in_(region_list))

    if genres:
        genre_list = [g.strip() for g in genres.split(",") if g.strip()]
        conditions = [Game.genre.ilike(f"%{g}%") for g in genre_list]
        q = q.filter(or_(*conditions))

    if series:
        q = q.filter(Game.series.ilike(f"%{series}%"))

    if year_min is not None:
        q = q.filter(Game.release_year >= year_min)
    if year_max is not None:
        q = q.filter(Game.release_year <= year_max)

    total = q.count()

    # Sorting
    sort_col = getattr(Game, sort_by, Game.sort_title)
    if sort_dir == "desc":
        q = q.order_by(sort_col.desc())
    else:
        q = q.order_by(sort_col.asc())

    items = q.offset((page - 1) * page_size).limit(page_size).all()

    result_items = []
    for game in items:
        system = game.system
        item = GameOut(
            id=game.id,
            title=game.title,
            sort_title=game.sort_title,
            system_id=game.system_id,
            system_name=system.name,
            system_esde_folder=system.esde_folder,
            region=game.region,
            languages=game.languages,
            series=game.series,
            genre=game.genre,
            publisher=game.publisher,
            developer=game.developer,
            release_year=game.release_year,
            description=game.description,
            cover_art_path=game.cover_art_path,
            screenshot_path=game.screenshot_path,
            no_intro_name=game.no_intro_name,
            rating=game.rating,
            players=game.players,
            rom_files=[RomFileOut.model_validate(rf) for rf in game.rom_files],
        )
        result_items.append(item)

    return GamesResponse(total=total, page=page, page_size=page_size, items=result_items)


@router.get("/filters")
def get_filter_options(db: Session = Depends(get_db)):
    """Return distinct values for all filter fields."""
    genres = [r[0] for r in db.query(Game.genre).distinct().filter(Game.genre.isnot(None)).all()]
    regions = [r[0] for r in db.query(Game.region).distinct().filter(Game.region.isnot(None)).all()]
    series_list = [r[0] for r in db.query(Game.series).distinct().filter(Game.series.isnot(None)).all()]
    years = [r[0] for r in db.query(Game.release_year).distinct().filter(Game.release_year.isnot(None)).order_by(Game.release_year).all()]

    return {
        "genres": sorted(g for g in genres if g),
        "regions": sorted(r for r in regions if r),
        "series": sorted(s for s in series_list if s),
        "years": years,
    }


@router.get("/stats")
def get_library_stats(db: Session = Depends(get_db)):
    total_games = db.query(func.count(Game.id)).scalar()
    total_systems = db.query(func.count(System.id)).filter(
        System.id.in_(db.query(Game.system_id).distinct())
    ).scalar()
    total_size = db.query(func.sum(RomFile.file_size)).scalar() or 0
    return {
        "total_games": total_games,
        "total_systems": total_systems,
        "total_size_bytes": total_size,
    }


@router.post("/rematch")
def rematch_library(db: Session = Depends(get_db)):
    """Re-scan loaded DAT files and update titles, No-Intro names, regions, and languages for existing ROMs."""
    from backend.config import settings
    from backend.services import dat_matcher, filename_parser, hasher

    dat_count = dat_matcher.load_all_dats()
    games = db.query(Game).all()
    updated_count = 0

    for game in games:
        if not game.rom_files:
            continue
        rf = game.rom_files[0]
        full_path = settings.library_dir / rf.library_path
        if full_path.exists():
            h = hasher.compute_hashes(full_path)
            entry = dat_matcher.lookup(crc32=h.crc32, md5=h.md5, sha1=h.sha1, hashes=h)
            if entry:
                game.title = entry.name
                game.sort_title = filename_parser.parse_rom_filename(entry.name).clean_title
                game.no_intro_name = entry.name
                game.region = entry.region
                if entry.languages:
                    game.languages = ",".join(entry.languages)
                rf.dat_matched = True
                updated_count += 1
            elif not game.no_intro_name:
                # Fallback clean title formatting
                parsed = filename_parser.parse_rom_filename(rf.original_filename)
                if parsed.clean_title:
                    game.title = parsed.clean_title
                    game.sort_title = parsed.clean_title

    db.commit()
    return {"updated": updated_count, "dats_loaded": dat_count}
