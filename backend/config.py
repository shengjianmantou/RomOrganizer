"""
Application configuration — reads from environment or .env file.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Library
    library_dir: Path = Path("library")
    dat_files_dir: Path = Path("dat_files")

    # Server
    host: str = "127.0.0.1"
    port: int = 8765

    # ScreenScraper
    screenscraper_user: str = ""
    screenscraper_password: str = ""
    screenscraper_devid: str = ""
    screenscraper_devpassword: str = ""

    # TheGamesDB
    thegamesdb_api_key: str = ""

    # IGDB / Twitch
    igdb_client_id: str = ""
    igdb_client_secret: str = ""

    # Scraping
    scrape_on_import: bool = True
    max_scrape_workers: int = 4

    @property
    def db_path(self) -> Path:
        return self.library_dir / "romorganizer.db"

    @property
    def files_dir(self) -> Path:
        return self.library_dir / "files"

    @property
    def media_dir(self) -> Path:
        return self.library_dir / "media"


settings = Settings()
