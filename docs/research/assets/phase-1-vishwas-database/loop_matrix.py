"""Which DB driver can share one event loop with Playwright on Windows?
Run with the BACKEND venv's python so Playwright 1.63 + its Chromium are available; sqlalchemy/drivers come from PYTHONPATH."""
import asyncio, time
from playwright.async_api import async_playwright
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DB = "krama:krama-local-only@127.0.0.1:5433/krama_research"

async def playwright_ok() -> str:
    async with async_playwright() as p:
        b = await p.chromium.launch()
        await b.close()
    return "ok"

async def db_ok(driver: str) -> str:
    eng = create_async_engine(f"postgresql+{driver}://{DB}")
    async with eng.connect() as c:
        await c.execute(text("select 1"))
    await eng.dispose()
    return "ok"

async def both(driver: str) -> None:
    for name, coro in [("playwright", playwright_ok()), (driver, db_ok(driver))]:
        try:
            async with asyncio.timeout(30):
                r = await coro
        except BaseException as e:
            r = f"FAIL {type(e).__name__}: {str(e)[:90]}"
        print(f"    {name:10} {r}", flush=True)

for loop_name, factory in [("Proactor (default)", None), ("Selector", asyncio.SelectorEventLoop)]:
    for driver in ["psycopg", "asyncpg"]:
        print(f"{loop_name} + {driver}:", flush=True)
        asyncio.run(both(driver), loop_factory=factory)
