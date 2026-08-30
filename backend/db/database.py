"""Database initialization and session management."""
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from backend.config import settings
from backend.db.models import Base, System
from backend.services.systems import SYSTEMS_REGISTRY


def _get_engine(db_path: Path | None = None):
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine


def init_db():
    """Create all tables, seed system definitions, and start fresh."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    _migrate_schema(engine)
    _seed_systems(engine)
    _clean_startup_library(engine)
    # Ensure media directory exists
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    settings.files_dir.mkdir(parents=True, exist_ok=True)


def _clean_startup_library(engine):
    """Ensure every start is a clean, fresh load."""
    try:
        with Session(engine) as session:
            from backend.db.models import RomFile, Game, ImportJob, ExportJob
            session.query(RomFile).delete()
            session.query(Game).delete()
            session.query(ImportJob).delete()
            session.query(ExportJob).delete()
            session.commit()
    except Exception:
        pass


def _migrate_schema(engine):
    """Safely apply schema migrations for SQLite."""
    with engine.connect() as conn:
        try:
            res = conn.exec_driver_sql("PRAGMA table_info(export_jobs)").fetchall()
            cols = {row[1] for row in res}
            if cols:
                if "rename_files" not in cols:
                    conn.exec_driver_sql("ALTER TABLE export_jobs ADD COLUMN rename_files BOOLEAN DEFAULT 1")
                if "only_preferred_languages" not in cols:
                    conn.exec_driver_sql("ALTER TABLE export_jobs ADD COLUMN only_preferred_languages BOOLEAN DEFAULT 0")
                conn.commit()
        except Exception:
            pass


def _seed_systems(engine):
    """Insert or update system records from the registry."""
    with Session(engine) as session:
        existing = {s.esde_folder: s for s in session.query(System).all()}
        for sys_def in SYSTEMS_REGISTRY:
            if sys_def["esde_folder"] not in existing:
                session.add(System(**sys_def))
        session.commit()


@contextmanager
def get_session():
    engine = get_engine()
    if _SessionLocal is None:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
    else:
        factory = _SessionLocal
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    """FastAPI dependency for DB sessions."""
    with get_session() as session:
        yield session
