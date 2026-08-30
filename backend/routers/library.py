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
    verified: Optional[str] = Query(None, enum=["all", "verified", "unverified"]),
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

    if verified == "verified":
        q = q.filter(Game.no_intro_name.isnot(None))
    elif verified == "unverified":
        q = q.filter(Game.no_intro_name.is_(None))

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


@router.get("/game-ids")
def get_all_game_ids(
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    system_ids: Optional[str] = None,
    languages: Optional[str] = None,
    regions: Optional[str] = None,
    genres: Optional[str] = None,
    series: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    verified: Optional[str] = Query(None, enum=["all", "verified", "unverified"]),
) -> list[int]:
    """Return all game IDs matching the given filters across all pages."""
    q = db.query(Game.id).join(System)

    if search:
        q = q.filter(Game.title.ilike(f"%{search}%"))
    if system_ids:
        ids = [int(x) for x in system_ids.split(",") if x.strip().isdigit()]
        if ids:
            q = q.filter(Game.system_id.in_(ids))
    if verified == "verified":
        q = q.filter(Game.no_intro_name.isnot(None))
    elif verified == "unverified":
        q = q.filter(Game.no_intro_name.is_(None))
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

    return [r[0] for r in q.all()]


@router.post("/clear")
def clear_library(db: Session = Depends(get_db)):
    """Clear all imported games and ROM files from the database and library storage."""
    import shutil
    from backend.config import settings

    db.query(RomFile).delete()
    db.query(Game).delete()
    db.commit()

    if settings.files_dir.exists():
        for item in settings.files_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)

    if settings.media_dir.exists():
        for item in settings.media_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)

    return {"status": "cleared", "total_games": 0}
def get_filter_options(
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    system_ids: Optional[str] = None,
    languages: Optional[str] = None,
    regions: Optional[str] = None,
    genres: Optional[str] = None,
    series: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    verified: Optional[str] = None,
):
    """Return distinct filter options along with dynamic availability counts based on active filters."""
    def _apply(q, skip: str | None = None):
        if search and skip != "search":
            q = q.filter(Game.title.ilike(f"%{search}%"))
        if system_ids and skip != "system_ids":
            ids = [int(x) for x in system_ids.split(",") if x.strip().isdigit()]
            if ids:
                q = q.filter(Game.system_id.in_(ids))
        if verified and skip != "verified":
            if verified == "verified":
                q = q.filter(Game.no_intro_name.isnot(None))
            elif verified == "unverified":
                q = q.filter(Game.no_intro_name.is_(None))
        if languages and skip != "languages":
            lang_list = [l.strip() for l in languages.split(",") if l.strip()]
            q = q.filter(or_(*[Game.languages.ilike(f"%{l}%") for l in lang_list]))
        if regions and skip != "regions":
            r_list = [r.strip() for r in regions.split(",") if r.strip()]
            q = q.filter(Game.region.in_(r_list))
        if genres and skip != "genres":
            g_list = [g.strip() for g in genres.split(",") if g.strip()]
            q = q.filter(or_(*[Game.genre.ilike(f"%{g}%") for g in g_list]))
        if series and skip != "series":
            q = q.filter(Game.series.ilike(f"%{series}%"))
        if year_min is not None and skip != "years":
            q = q.filter(Game.release_year >= year_min)
        if year_max is not None and skip != "years":
            q = q.filter(Game.release_year <= year_max)
        return q

    # 1. System counts (evaluated against all filters except system_ids)
    q_sys = _apply(db.query(Game), skip="system_ids")
    sys_counts = {
        r[0]: r[1]
        for r in q_sys.with_entities(Game.system_id, func.count(Game.id)).group_by(Game.system_id).all()
    }

    # 2. Languages available (evaluated against all filters except languages)
    q_lang = _apply(db.query(Game), skip="languages")
    raw_langs = [r[0] for r in q_lang.with_entities(Game.languages).distinct().filter(Game.languages.isnot(None)).all()]
    available_languages = sorted({l.strip() for r in raw_langs for l in r.split(",") if l.strip()})

    # 3. Regions available (evaluated against all filters except regions)
    q_reg = _apply(db.query(Game), skip="regions")
    available_regions = sorted(r[0] for r in q_reg.with_entities(Game.region).distinct().filter(Game.region.isnot(None)).all() if r[0])

    # 4. Genres available (evaluated against all filters except genres)
    q_gen = _apply(db.query(Game), skip="genres")
    available_genres = sorted(r[0] for r in q_gen.with_entities(Game.genre).distinct().filter(Game.genre.isnot(None)).all() if r[0])

    # 5. Series available (evaluated against all filters except series)
    q_ser = _apply(db.query(Game), skip="series")
    available_series = sorted(r[0] for r in q_ser.with_entities(Game.series).distinct().filter(Game.series.isnot(None)).all() if r[0])

    # 6. Verification counts (evaluated against all filters except verified)
    q_ver = _apply(db.query(Game), skip="verified")
    verified_count = q_ver.filter(Game.no_intro_name.isnot(None)).count()
    unverified_count = q_ver.filter(Game.no_intro_name.is_(None)).count()

    # 7. Global distinct options for static dropdowns
    all_genres = [r[0] for r in db.query(Game.genre).distinct().filter(Game.genre.isnot(None)).all() if r[0]]
    all_regions = [r[0] for r in db.query(Game.region).distinct().filter(Game.region.isnot(None)).all() if r[0]]
    all_series = [r[0] for r in db.query(Game.series).distinct().filter(Game.series.isnot(None)).all() if r[0]]
    years = [r[0] for r in db.query(Game.release_year).distinct().filter(Game.release_year.isnot(None)).order_by(Game.release_year).all()]

    return {
        "genres": sorted(all_genres),
        "regions": sorted(all_regions),
        "series": sorted(all_series),
        "years": years,
        "system_counts": sys_counts,
        "available_system_ids": list(sys_counts.keys()),
        "available_languages": available_languages,
        "available_regions": available_regions,
        "available_genres": available_genres,
        "available_series": available_series,
        "verified_count": verified_count,
        "unverified_count": unverified_count,
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
