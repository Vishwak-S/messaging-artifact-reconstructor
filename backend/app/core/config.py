from pydantic_settings import BaseSettings
from pathlib import Path
import os

# Store DB in a path guaranteed to have no spaces (home dir / AppData)
_DATA_DIR = Path.home() / "forensic_reconstructor_data"
_DB_PATH = (_DATA_DIR / "forensic_app.db").as_posix()
_EVIDENCE_DIR = _DATA_DIR / "evidence_store"
_REPORTS_DIR = _DATA_DIR / "reports_output"

# Ensure directories exist before settings are loaded
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DB_URL: str = f"sqlite:///{_DB_PATH}"
    EVIDENCE_STORE: str = str(_EVIDENCE_DIR)
    REPORTS_DIR: str = str(_REPORTS_DIR)
    APP_VERSION: str = "1.1.0"
    PARSER_VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
