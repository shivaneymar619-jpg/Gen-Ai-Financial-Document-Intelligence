"""Application configuration.

All settings are env-overridable. The defaults are chosen so the app runs
out-of-the-box on localhost with zero external services. To scale up:
  - DATABASE_URL: swap SQLite for "postgresql+psycopg://user:pass@host/db"
  - STORAGE_DIR : swap for an S3-backed mount / boto3 layer
  - GEMINI_API_KEY: enables real LLM answer generation (otherwise extractive fallback)
"""
import os
from pathlib import Path
from functools import lru_cache

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings:
    APP_NAME: str = "FinDocAI"
    API_PREFIX: str = "/api"

    # --- Database (SQLite by default; Postgres-compatible) ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'findocai.db'}")

    # --- Auth / JWT ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production-0xCAFEBABE")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # --- Storage (local disk; S3-swappable) ---
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", str(DATA_DIR / "uploads")))

    # --- Vector store (persistent Chroma if available, else SQLite-backed fallback) ---
    CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma")))

    # --- LLM ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-2.5-flash")

    # --- Freemium limits ---
    FREE_DOC_LIMIT: int = int(os.getenv("FREE_DOC_LIMIT", "10"))
    FREE_QUERY_LIMIT: int = int(os.getenv("FREE_QUERY_LIMIT", "100"))

    # --- Misc ---
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RETRIEVE_K: int = 5

    def __init__(self):
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.CHROMA_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> "Settings":
    return Settings()


settings = get_settings()
