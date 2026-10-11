"""Does async psycopg 3 work on Windows' default (Proactor) event loop? Each attempt is capped at 15 s."""
import asyncio, sys, time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
URL = "postgresql+psycopg://krama:krama-local-only@127.0.0.1:5433/krama_research"
async def main() -> None:
    async with asyncio.timeout(15):
        eng = create_async_engine(URL)
        async with eng.connect() as c:
            print("  select 1 ->", (await c.execute(text("select 1"))).scalar(), flush=True)
        await eng.dispose()
print("python", sys.version.split()[0], sys.platform, flush=True)
for name, factory in [("default (Proactor)", None), ("SelectorEventLoop", asyncio.SelectorEventLoop)]:
    t = time.perf_counter()
    try:
        asyncio.run(main(), loop_factory=factory)
        print(f"{name}: OK in {time.perf_counter()-t:.2f}s", flush=True)
    except BaseException as e:
        print(f"{name}: FAILED {type(e).__name__}: {str(e)[:200]}", flush=True)
