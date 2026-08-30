"""Systems router."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import System

router = APIRouter(prefix="/api/systems", tags=["systems"])


class SystemOut(BaseModel):
    id: int
    name: str
    esde_folder: str
    extensions: str
    manufacturer: Optional[str] = None
    release_year: Optional[int] = None
    screenscraper_id: Optional[int] = None
    thegamesdb_id: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[SystemOut])
def list_systems(db: Session = Depends(get_db)):
    return db.query(System).order_by(System.name).all()
