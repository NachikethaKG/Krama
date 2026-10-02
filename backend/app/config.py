"""Runtime settings, read from the repo-root `.env` (see `.env.example`)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_version: str = "0.1.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str = "postgresql+psycopg://krama:krama-local-only@localhost:5433/krama"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: str = ""

    artifacts_dir: Path = REPO_ROOT / "data" / "artifacts"
    max_concurrent_runs: int = 1


@lru_cache
def get_settings() -> Settings:
    return Settings()
