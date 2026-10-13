"""Shared fixtures: a real Postgres for the tests that need it (tests/db, tests/runs, tests/api).

A throwaway `krama_test` database next to the dev one, migrated with `alembic upgrade head`. Start Postgres
with `just up`. Without it these tests skip, except in CI (`KRAMA_REQUIRE_DB=1`), where a missing database
is a failure.
"""

import asyncio
import os
import threading
from collections.abc import AsyncIterator, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

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


# A tiny real website for end-to-end runs without Gitea: real HTTP, real navigations.
PAGES: dict[str, str] = {
    "/": """<!doctype html><title>Home</title><main><h1>Home</h1>
        <a href="/form">New item</a>
        <a href="/slow">Slow page</a></main>""",
    "/form": """<!doctype html><title>New item</title><main><h1>New item</h1>
        <form action="/done" method="post">
          <label>Item name * <input name="item"></label>
          <label>Password <input name="pw" type="password"></label>
          <label><input type="checkbox" name="init"> Add a README</label>
          <button type="submit">Create item</button>
        </form></main>""",
    "/done": "<!doctype html><title>Item created</title><main><h1>Item created</h1></main>",
    # Navigates on its own after 600 ms: verification must wait for it instead of failing at once.
    "/slow": """<!doctype html><title>Slow</title><main><h1>Slow</h1>
        <script>setTimeout(() => { location.href = "/done" }, 600)</script></main>""",
}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = PAGES.get(urlsplit(self.path).path)
        self.send_response(200 if body else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((body or "<title>Not found</title>").encode())

    def do_POST(self) -> None:
        # Like a real form: the body (with the password) is discarded and the browser is redirected.
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(303)
        self.send_header("Location", "/done")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
