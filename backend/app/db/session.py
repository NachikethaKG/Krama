"""Engine and session factory. asyncpg, because it works on Windows's Proactor loop next to Playwright.

Request handlers get one session per request (#48). The run executor never borrows a request's session: it
opens a short transaction per transition or event (`async with sessions.begin() as session:`).
"""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def create_engine(url: str | None = None) -> AsyncEngine:
    url = url or get_settings().database_url
    if not url.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL must use the asyncpg driver: postgresql+asyncpg://…")
    return create_async_engine(url, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: reading an attribute after commit must not trigger implicit (async) IO.
    return async_sessionmaker(engine, expire_on_commit=False)
