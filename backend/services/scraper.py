"""
Metadata scraper — fetches game info from ScreenScraper, TheGamesDB, and IGDB.
Falls back gracefully through sources.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from backend.config import settings

log = logging.getLogger(__name__)


@dataclass
class GameMetadata:
    title: Optional[str] = None
    description: Optional[str] = None
    genre: Optional[str] = None
    publisher: Optional[str] = None
    developer: Optional[str] = None
    release_year: Optional[int] = None
    rating: Optional[float] = None
    players: Optional[int] = None
    series: Optional[str] = None
    cover_art_url: Optional[str] = None
    screenshot_url: Optional[str] = None
    screenscraper_id: Optional[int] = None
    source: str = "unknown"


class ScreenScraperClient:
    BASE = "https://www.screenscraper.fr/api2"

    def __init__(self):
        self.user = settings.screenscraper_user
        self.password = settings.screenscraper_password
        self.devid = settings.screenscraper_devid or "romorganizer"
        self.devpassword = settings.screenscraper_devpassword or ""

    def _base_params(self) -> dict:
        return {
            "devid": self.devid,
            "devpassword": self.devpassword,
            "softname": "romorganizer",
            "output": "json",
            "ssid": self.user,
            "sspassword": self.password,
        }

    async def search_by_hash(
        self,
        system_id: int,
        crc32: str | None = None,
        md5: str | None = None,
        sha1: str | None = None,
        filename: str | None = None,
    ) -> Optional[GameMetadata]:
        if not self.user or not self.password:
            return None
        params = {**self._base_params(), "systemeid": system_id}
        if crc32:
            params["crc"] = crc32
        if md5:
            params["md5"] = md5
        if sha1:
            params["sha1"] = sha1
        if filename:
            params["romfilename"] = filename
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.BASE}/jeuInfos.php", params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                return self._parse_response(data)
        except Exception as e:
            log.debug(f"ScreenScraper error: {e}")
            return None

    def _parse_response(self, data: dict) -> Optional[GameMetadata]:
        try:
            jeu = data["response"]["jeu"]
            meta = GameMetadata(source="screenscraper")
            meta.screenscraper_id = int(jeu.get("id", 0)) or None

            # Title (prefer English)
            for nom in jeu.get("noms", []):
                if nom.get("region") in ("us", "wor", "eu"):
                    meta.title = nom.get("text")
                    break
            if not meta.title and jeu.get("noms"):
                meta.title = jeu["noms"][0].get("text")

            # Description
            for synopsis in jeu.get("synopsis", []):
                if synopsis.get("langue") == "en":
                    meta.description = synopsis.get("text")
                    break
            if not meta.description and jeu.get("synopsis"):
                meta.description = jeu["synopsis"][0].get("text")

            # Genre
            genres = jeu.get("genres", [])
            if genres:
                for g in genres:
                    for gn in g.get("noms", []):
                        if gn.get("langue") == "en":
                            meta.genre = gn.get("text")
                            break
                    if meta.genre:
                        break

            # Publisher / Developer
            for company in jeu.get("editeurs", []):
                meta.publisher = company.get("editeur", {}).get("text")
                break
            for company in jeu.get("developpeurs", []):
                meta.developer = company.get("developpeur", {}).get("text")
                break

            # Release year
            dates = jeu.get("dates", [])
            for d in dates:
                if d.get("region") in ("us", "wor", "eu"):
                    try:
                        meta.release_year = int(d["text"][:4])
                    except (ValueError, TypeError, KeyError):
                        pass
                    break

            # Rating
            note = jeu.get("note")
            if note:
                try:
                    meta.rating = float(note) / 20.0  # SS uses 0-20
                except (ValueError, TypeError):
                    pass

            # Players
            joueurs = jeu.get("joueurs", {}).get("text")
            if joueurs:
                try:
                    meta.players = int(joueurs.split("-")[0])
                except (ValueError, AttributeError):
                    pass

            # Media URLs
            for media in jeu.get("medias", []):
                type_ = media.get("type")
                url = media.get("url")
                if not url:
                    continue
                if type_ in ("box-2D", "box-3D", "mixrbv1") and not meta.cover_art_url:
                    meta.cover_art_url = url
                elif type_ == "ss" and not meta.screenshot_url:
                    meta.screenshot_url = url

            return meta
        except (KeyError, TypeError, IndexError) as e:
            log.debug(f"ScreenScraper parse error: {e}")
            return None


class TheGamesDBClient:
    BASE = "https://api.thegamesdb.net/v1"

    async def search(
        self, title: str, platform_id: int | None = None
    ) -> Optional[GameMetadata]:
        if not settings.thegamesdb_api_key:
            return None
        params = {
            "apikey": settings.thegamesdb_api_key,
            "name": title,
            "fields": "players,publishers,developers,rating,genres,overview",
            "include": "boxart",
        }
        if platform_id:
            params["filter[platform]"] = platform_id
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.BASE}/Games/ByGameName", params=params)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                games = data.get("data", {}).get("games", [])
                if not games:
                    return None
                return self._parse_game(games[0], data)
        except Exception as e:
            log.debug(f"TheGamesDB error: {e}")
            return None

    def _parse_game(self, game: dict, full_data: dict) -> GameMetadata:
        meta = GameMetadata(source="thegamesdb")
        meta.title = game.get("game_title")
        meta.description = game.get("overview")
        meta.release_year = None
        release = game.get("release_date", "")
        if release:
            try:
                meta.release_year = int(release[:4])
            except (ValueError, TypeError):
                pass
        meta.rating = game.get("rating")
        meta.players = game.get("players")
        # Boxart
        boxart = full_data.get("include", {}).get("boxart", {})
        base_url = boxart.get("base_url", {}).get("medium", "")
        images = boxart.get("data", {}).get(str(game.get("id")), [])
        for img in images:
            if img.get("side") == "front":
                meta.cover_art_url = base_url + img.get("filename", "")
                break
        return meta


async def download_image(url: str, dest: Path) -> bool:
    """Download an image URL to a local path."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)
                return True
    except Exception as e:
        log.debug(f"Image download failed {url}: {e}")
    return False


async def fetch_metadata(
    title: str,
    system_screenscraper_id: int | None = None,
    system_thegamesdb_id: int | None = None,
    crc32: str | None = None,
    md5: str | None = None,
    sha1: str | None = None,
    filename: str | None = None,
) -> Optional[GameMetadata]:
    """
    Try metadata sources in order: ScreenScraper -> TheGamesDB.
    Returns first successful result.
    """
    # 1. ScreenScraper
    if system_screenscraper_id:
        ss = ScreenScraperClient()
        meta = await ss.search_by_hash(
            system_id=system_screenscraper_id,
            crc32=crc32,
            md5=md5,
            sha1=sha1,
            filename=filename,
        )
        if meta and meta.title:
            return meta

    # 2. TheGamesDB
    tgdb = TheGamesDBClient()
    meta = await tgdb.search(title=title, platform_id=system_thegamesdb_id)
    if meta and meta.title:
        return meta

    return None
