"""Runtime settings, read from the repo-root `.env` (see `.env.example`)."""

from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_version: str = "0.1.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    # Where share links point (#96): the frontend's /share/<token> page.
    frontend_url: str = "http://localhost:3000"

    # 127.0.0.1, not localhost: on Windows + Docker Desktop, localhost tries IPv6 first and asyncpg waits
    # ~21 s for it to time out before falling back to IPv4.
    database_url: str = "postgresql+asyncpg://krama:krama-local-only@127.0.0.1:5433/krama"
    # 127.0.0.1 too: arq's async client times out on IPv6 localhost (phase-3-vishwas-job-queue.md).
    redis_url: str = "redis://127.0.0.1:6379/0"
    # inprocess: runs execute inside the API (tests, no Redis). arq: in the worker (#95).
    run_executor: Literal["inprocess", "arq"] = "inprocess"

    llm_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: str = ""
    # Tried in order; each model has its own free-tier quota (docs/research/phase-0-vishwas-gemini-*).
    gemini_models: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-2.5-flash"

    # Local-only demo account on the test Gitea (`just seed`).
    gitea_url: str = "http://localhost:3001"
    gitea_demo_user: str = "demo"
    gitea_demo_password: str = "demo-local-only"

    # The GitHub test account (docs/research/phase-3-together-github-account-and-benchmarks.md). Runs use its
    # stored, encrypted browser session (#87); Krama never has its password.
    github_url: str = "https://github.com"
    github_test_user: str = ""
    github_test_org: str = ""
    # The test org's fine-grained token (resource owner = the org). Used only to keep the practice repository
    # (#325) in place: tasks that need an existing repository and name none run there. A secret: never logged.
    github_bench_token: SecretStr = SecretStr("")
    github_api_url: str = "https://api.github.com"
    # bench-* so the account rules allow it and scripts/github_cleanup.py clears it (recreated on demand).
    github_practice_repo: str = "bench-practice"
    # Fernet key(s) for stored browser sessions, newest first, comma-separated (`krama session key`).
    krama_storage_key: SecretStr = SecretStr("")
    sessions_dir: Path = REPO_ROOT / "data" / "sessions"

    # Sign-in sessions (#94): an HTTP-only cookie. Secure only behind HTTPS (browsers drop Secure cookies on
    # plain http, except on localhost in some browsers).
    session_cookie_name: str = "krama_session"
    session_cookie_secure: bool = False
    session_idle: timedelta = timedelta(days=7)
    session_absolute: timedelta = timedelta(days=30)
    # The seeded demo account (`krama users seed`): demo@krama.dev with this password (15+ characters).
    krama_demo_password: SecretStr = SecretStr("")

    artifacts_dir: Path = REPO_ROOT / "data" / "artifacts"

    # Narration for video export (#120, docs/adr/0004): Piper runs in backend/tts-worker (GPL, own venv) as a
    # subprocess. `just backend tts-setup` installs it and downloads the voice into tts_voices_dir.
    tts_voice: str = "en_US-ljspeech-medium"
    tts_voices_dir: Path = REPO_ROOT / "data" / "tts" / "voices"
    tts_worker_dir: Path = REPO_ROOT / "backend" / "tts-worker"
    # onnxruntime threads in the worker. The default (one per core) stalls while Chromium or Remotion run.
    tts_threads: int = Field(default=2, ge=1, le=16)

    # Export cleanup (#125, D18): a daily cron in `just backend worker`, or `krama exports cleanup`.
    # Exports and unused narration clips older than this go; the newest export per version and preset stays.
    exports_retention_days: int = Field(default=30, ge=1)
    # Disk cap for exports/ (GB). Above it, the oldest exports go first, protected ones only as a last resort.
    exports_max_gb: float = Field(default=5.0, gt=0)
    # Written by the benchmark reporter, served by GET /metrics/summary (#102).
    metrics_summary_path: Path = REPO_ROOT / "benchmarks" / "results" / "summary.json"
    max_concurrent_runs: int = 1
    # Recovery budget per run (phase-1-vishwas-agent-recovery.md). Running time only: pauses not counted.
    run_timeout_seconds: float = 600.0
    max_replans_per_run: int = 3

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]

    @field_validator(
        "artifacts_dir", "sessions_dir", "metrics_summary_path", "tts_voices_dir", "tts_worker_dir"
    )
    @classmethod
    def _relative_to_repo_root(cls, v: Path) -> Path:
        # `.env` paths like ./data/artifacts mean the repo root, not whatever folder the process started in.
        return v if v.is_absolute() else REPO_ROOT / v


@lru_cache
def get_settings() -> Settings:
    return Settings()
