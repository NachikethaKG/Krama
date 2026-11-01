"""`uvicorn app.main:app`. Dev: `just backend dev` (uses `--loop app.dev_loop:factory`)."""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import artifacts, auth, exports, health, metrics, plans, runs, shares, tasks, workflows
from app.api.csrf import CsrfMiddleware
from app.api.errors import ERROR_RESPONSES, install_error_handlers
from app.api.services import Services, build_services
from app.config import get_settings

API_PREFIX = "/api/v1"


def create_app(services: Services | None = None) -> FastAPI:
    """`services` lets tests inject their own; by default the real ones are built at startup."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        check_event_loop()
        svc = services or build_services(settings)
        app.state.services = svc
        await svc.start()
        try:
            yield
        finally:
            await svc.close()

    app = FastAPI(
        title="Krama API", version=settings.app_version, responses=ERROR_RESPONSES, lifespan=lifespan
    )
    # Middleware runs outside-in in reverse order of adding: CORS answers preflights before the CSRF check.
    app.add_middleware(CsrfMiddleware, allowed_origins=settings.cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # explicit origins: required with credentials (cookies)
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for module in (health, auth, tasks, plans, runs, workflows, exports, artifacts, shares, metrics):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


def check_event_loop() -> None:
    """Runs execute in this process and Playwright starts Chromium as a subprocess. On Windows only the
    Proactor loop can do that; uvicorn picks the Selector loop with --reload (phase-1-vishwas-database.md)."""
    loop = asyncio.get_running_loop()
    if sys.platform == "win32" and not isinstance(loop, asyncio.ProactorEventLoop):
        raise RuntimeError(
            f"{type(loop).__name__} can't start the browser on Windows. "
            "Run uvicorn with `--loop app.dev_loop:factory` (as `just backend dev` does)."
        )


app = create_app()
