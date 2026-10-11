# SQLAlchemy 2 + Alembic on Windows: driver, event loop, sessions, autogenerate

- **Phase:** 1
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **SQLAlchemy 2 + Alembic:** async engine with psycopg 3, the session-per-request pattern in FastAPI, Alembic autogenerate and its limits (it misses some changes).

## Findings
Experiments ran on 2026-10-11 on Windows 11 with Python 3.12.14 and Postgres 16.15 (Docker), in a throwaway venv: SQLAlchemy 2.1.4, Alembic 1.20.0, psycopg 3.3.6, asyncpg 0.32.0, uvicorn 0.54.0, Playwright 1.63 (backend venv). Scripts: [`assets/phase-1-vishwas-database/`](assets/phase-1-vishwas-database/)

### 1. The big one: async psycopg 3 and Playwright can't share an event loop on Windows
- psycopg's docs: "On Windows, Psycopg is not compatible with the default ProactorEventLoop" [verified: https://www.psycopg.org/psycopg3/docs/advanced/async.html]. On the default loop it raises `InterfaceError: Psycopg cannot use the 'ProactorEventLoop' to run in async mode` [verified locally: `pg_loop.py`].
- Playwright launches Chromium as a subprocess. On Windows only the Proactor loop supports subprocesses, so on the Selector loop `chromium.launch()` raises `NotImplementedError` [verified locally: `loop_matrix.py`].
- Architecture says jobs run **in-process asyncio in Phases 0–2** (`architecture.md`), so the run executor (Playwright) and the API's DB access share one process and one loop.

| Loop | Playwright | psycopg 3 async | asyncpg |
|---|---|---|---|
| Proactor (Windows default) | ✅ | ❌ InterfaceError | ✅ |
| Selector | ❌ NotImplementedError | ✅ | ✅ |

[verified locally: `loop_matrix.py`]

- **uvicorn picks the loop, and `--reload` changes it.** uvicorn 0.54 uses Proactor on Windows, but **Selector when `--reload` or `--workers` is used** (`uvicorn/loops/asyncio.py`: `if sys.platform == "win32" and not use_subprocess: return ProactorEventLoop`). Our `just dev` runs `uvicorn app.main:app --reload`, so **in dev mode Playwright can't launch inside the API at all, whichever driver we choose** [verified locally: `uvicorn_pw.py` returned `{"loop": "_WindowsSelectorEventLoop", "playwright": "FAIL NotImplementedError"}`].
- **Fix that works:** pass uvicorn a custom loop factory, `--loop proactor_loop:factory`, where `factory()` returns `asyncio.ProactorEventLoop()`. With `--reload` the server then served requests on `ProactorEventLoop` and Playwright launched inside the request [verified locally: `{"loop": "ProactorEventLoop", "playwright": "launched"}`]. uvicorn chose Selector for reload because of historical socket-sharing issues; the dev server worked fine in our test, but this is the less-trodden path [unverified: why uvicorn made that choice].
- Python's docs confirm the root cause: on Windows, `ProactorEventLoop` (the default since 3.8) "supports subprocesses, whereas SelectorEventLoop does not" [verified: https://docs.python.org/3.12/library/asyncio-platforms.html#windows].
- Linux (CI, Docker) has none of this: both drivers and Playwright work on the default loop. **So CI would pass while a Windows laptop fails**, which matters because the exit criteria run on Nachiketha's Windows laptop.
- Licenses: asyncpg Apache-2.0; psycopg LGPL-3.0-only (fine to use as a library) [verified locally: package metadata].

### 2. Session per request in FastAPI (SQLAlchemy 2 async)
The pattern, tested in the SSE and persistence experiments:
```python
engine = create_async_engine("postgresql+asyncpg://…", pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:   # one session per request, closed after the response
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
```
- `expire_on_commit=False`: the docs say it "should normally be set to False when using asyncio", because otherwise reading an attribute after `commit()` reloads it from the DB, and async code must avoid that implicit IO [verified: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html, "Preventing Implicit IO when Using AsyncSession"]. (In practice the error is `MissingGreenlet` [unverified: not named on that page].)
- **A background run must not use the request's session.** The request ends right after `POST /runs` returns, and its session closes with it. The executor opens its own short session or transaction per transition and per event (as in `persist.py`). "A single instance of AsyncSession is not safe for use in multiple, concurrent tasks" [verified: same SQLAlchemy page, "Using AsyncSession with Concurrent Tasks"].
- **Pitfall found:** a plain `Mapped[datetime]` creates `timestamp without time zone` [verified locally: `information_schema` after the first migration showed `created_at | timestamp without time zone`]. Our schema says every timestamp is `timestamptz`, so set `type_annotation_map = {datetime: DateTime(timezone=True)}` on the declarative `Base`.

### 3. Alembic autogenerate: what it catches and what it misses
Method: create a v1 table, then ask `compare_metadata` about one edit at a time [verified locally: `alembic_probe.py`]. `alembic init -t async` gives a working async `env.py` [verified locally].

| Edit | Default settings | With `compare_server_default=True` |
|---|---|---|
| Add column / index / unique constraint | ✅ detected | ✅ |
| Column type or length (`String(20)`→`String(50)`, `timestamptz`→`timestamp`) | ✅ (`compare_type` is on by default) | ✅ |
| nullable → NOT NULL | ✅ | ✅ |
| Server default `'0'`→`'1'` | ❌ **missed** | ✅ |
| CHECK constraint values changed | ❌ **missed** | ❌ **missed** |
| Postgres ENUM gains a value | ❌ **missed** | ❌ **missed** |
| Column **rename** | ⚠️ emitted as **drop + add** (data loss if applied as is) | same |

This matches the docs: autogenerate "can not detect" table or column renames, server defaults need `compare_server_default=True`, and type comparison is on by default. Alembic 1.19+ has an opt-in plugin, `alembic.ext.checkconstraint_byname` (via `autogenerate_plugins`), that detects **added or removed named** CHECK constraints, but "Expression changes are never detected", so our case (same name, new value list) stays invisible [verified: https://alembic.sqlalchemy.org/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect and #detecting-check-constraints].

## Recommendation
Decisions (Vishwas, 2026-10-11):
- **Driver: asyncpg** (`postgresql+asyncpg://`). It works on both Windows loops, so the in-process executor (Playwright) and the DB share one Proactor loop. Not psycopg 3: its async mode needs the Selector loop, which breaks Playwright.
- **Dev server: run uvicorn on Proactor even with `--reload`**: `uvicorn app.main:app --reload --loop app.dev_loop:factory` (a 3-line module). This is required whatever the driver. Add a test that fails if the running loop can't start a subprocess, so the problem surfaces in our own suite.
- **Sessions:** `async_sessionmaker(expire_on_commit=False)`, session per request via a dependency, and separate short sessions inside the run executor. `type_annotation_map` → `DateTime(timezone=True)`.
- **Alembic:** start from `alembic init -t async` and set `compare_server_default=True`. Use `text` + named CHECK constraints for statuses, not Postgres ENUMs (ENUMs are harder to change). **Review every generated migration by hand**, especially CHECK changes (write `op.drop_constraint` + `op.create_constraint` yourself) and renames (`op.alter_column(new_column_name=…)`). Never edit a migration already on `main` (AGENTS.md rule 6).
- No ADR: the fixed decision is "SQLAlchemy 2 + Alembic"; the driver was only a research question. The phase file's mention of psycopg 3 should be updated to asyncpg (suggested in the PR, not changed here).
- Phase 3 moves runs to a Redis + arq worker process. Then the API process no longer needs Playwright, and the loop constraint applies only to the worker.

## Open questions
- Does `--loop app.dev_loop:factory` behave on Nachiketha's laptop too (same uvicorn version)? Check when #48 lands; it's a one-line `curl` against a debug endpoint.

## Links
- https://www.psycopg.org/psycopg3/docs/advanced/async.html
- https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- https://alembic.sqlalchemy.org/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect
- https://github.com/encode/uvicorn/blob/master/uvicorn/loops/asyncio.py
- https://docs.python.org/3.12/library/asyncio-platforms.html#windows (subprocesses need the Proactor loop on Windows)
