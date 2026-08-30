"""Settings router — manage library config and API credentials."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Setting
from backend.services import dat_matcher

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    screenscraper_user: str = ""
    screenscraper_password: str = ""
    thegamesdb_api_key: str = ""
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    scrape_on_import: bool = True


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    rows = {r.key: r.value for r in db.query(Setting).all()}
    return {
        "screenscraper_user": rows.get("screenscraper_user", ""),
        "screenscraper_password": "***" if rows.get("screenscraper_password") else "",
        "thegamesdb_api_key": "***" if rows.get("thegamesdb_api_key") else "",
        "igdb_client_id": rows.get("igdb_client_id", ""),
        "igdb_client_secret": "***" if rows.get("igdb_client_secret") else "",
        "scrape_on_import": rows.get("scrape_on_import", "true") == "true",
        "dat_stats": dat_matcher.get_dat_stats(),
    }


@router.put("")
def update_settings(payload: SettingsPayload, db: Session = Depends(get_db)):
    def _upsert(key: str, value: str):
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            if value:
                row.value = value
        else:
            db.add(Setting(key=key, value=value))

    _upsert("screenscraper_user", payload.screenscraper_user)
    if payload.screenscraper_password and payload.screenscraper_password != "***":
        _upsert("screenscraper_password", payload.screenscraper_password)
    if payload.thegamesdb_api_key and payload.thegamesdb_api_key != "***":
        _upsert("thegamesdb_api_key", payload.thegamesdb_api_key)
    _upsert("igdb_client_id", payload.igdb_client_id)
    if payload.igdb_client_secret and payload.igdb_client_secret != "***":
        _upsert("igdb_client_secret", payload.igdb_client_secret)
    _upsert("scrape_on_import", "true" if payload.scrape_on_import else "false")
    db.commit()
    return {"ok": True}


@router.get("/dat-stats")
def dat_stats():
    return dat_matcher.get_dat_stats()
