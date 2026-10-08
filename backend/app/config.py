"""Runtime settings, read from the repo-root `.env` (see `.env.example`)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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
    # Tried in order; each model has its own free-tier quota (docs/research/phase-0-vishwas-gemini-*).
    gemini_models: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-2.5-flash"

    # Local-only demo account on the test Gitea (`just seed`).
    gitea_demo_user: str = "demo"
    gitea_demo_password: str = "demo-local-only"

    artifacts_dir: Path = REPO_ROOT / "data" / "artifacts"
    max_concurrent_runs: int = 1

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    @field_validator("artifacts_dir")
    @classmethod
    def _relative_to_repo_root(cls, v: Path) -> Path:
        # `.env` paths like ./data/artifacts mean the repo root, not whatever folder the process started in.
        return v if v.is_absolute() else REPO_ROOT / v


@lru_cache
def get_settings() -> Settings:
    return Settings()
