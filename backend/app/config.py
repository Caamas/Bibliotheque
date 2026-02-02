from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Bibliotheque"
    DATABASE_URL: str = "sqlite+aiosqlite:///./bibliotheque.db"
    UPLOAD_DIR: Path = Path(__file__).parent.parent / "uploads"
    COVERS_DIR: Path = UPLOAD_DIR / "covers"
    SIGNATURES_DIR: Path = UPLOAD_DIR / "signatures"
    SHELVES_DIR: Path = UPLOAD_DIR / "shelves"

    # External APIs
    OPEN_LIBRARY_BASE_URL: str = "https://openlibrary.org"
    GOOGLE_BOOKS_BASE_URL: str = "https://www.googleapis.com/books/v1"
    GOOGLE_BOOKS_API_KEY: str = ""  # Optional, works without key with rate limits

    # Lending reminders
    DEFAULT_LENDING_DAYS: int = 30
    REMINDER_CHECK_INTERVAL_HOURS: int = 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure upload directories exist
for d in [settings.COVERS_DIR, settings.SIGNATURES_DIR, settings.SHELVES_DIR]:
    d.mkdir(parents=True, exist_ok=True)
