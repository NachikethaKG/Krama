"""Shared fixtures: a real Postgres for the tests that need it (tests/db, tests/runs, tests/api).

A throwaway `krama_test` database next to the dev one, migrated with `alembic upgrade head`. Start Postgres
with `just up`. Without it these tests skip, except in CI (`KRAMA_REQUIRE_DB=1`), where a missing database
is a failure.
"""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.config import get_settings
from app.db import Base, create_engine, create_sessionmaker

BACKEND = Path(__file__).resolve().parents[1]
TEST_DB = "krama_test"


def alembic_config(url: str) -> Config:
    cfg = Config(BACKEND / "alembic.ini")
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.attributes["configure_logger"] = False
    return cfg


async def _recreate_database(admin_url: str, name: str, *, drop_only: bool = False) -> None:
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            if not drop_only:
                await conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def test_db_url() -> Iterator[str]:
    """URL of a fresh, fully migrated test database (once per test session)."""
    admin_url = get_settings().database_url
    try:
        asyncio.run(asyncio.wait_for(_recreate_database(admin_url, TEST_DB), timeout=10))
    except (OSError, TimeoutError, DBAPIError) as e:
        where = make_url(admin_url).render_as_string()  # password hidden
        message = f"Postgres not reachable at {where}: start it with `just up` ({type(e).__name__})"
        if os.environ.get("KRAMA_REQUIRE_DB") == "1":
            pytest.fail(message)
        pytest.skip(message)
    url = make_url(admin_url).set(database=TEST_DB).render_as_string(hide_password=False)
    command.upgrade(alembic_config(url), "head")
    yield url
    asyncio.run(_recreate_database(admin_url, TEST_DB, drop_only=True))


@pytest.fixture
async def sessions(test_db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory on the test database. Every table is emptied after the test."""
    engine = create_engine(test_db_url)
    try:
        yield create_sessionmaker(engine)
    finally:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        await engine.dispose()
