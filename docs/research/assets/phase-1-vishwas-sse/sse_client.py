import asyncio, time, uuid, httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
BASE = "http://127.0.0.1:8770"

async def read(c: httpx.AsyncClient, path: str, last: int | None, n: int, raw: bool = False) -> list[str]:
    headers = {"Last-Event-ID": str(last)} if last is not None else {}
    out: list[str] = []
    async with c.stream("GET", path, headers=headers) as r:
        if raw:
            print("   headers:", {k: r.headers.get(k) for k in ("content-type", "cache-control", "x-accel-buffering")})
        async for line in r.aiter_lines():
            if line.startswith(("id:", ":")):
                out.append(line.strip())
                if (sum(1 for x in out if x.startswith("id:")) >= n) or (not raw and len(out) >= n and all(x.startswith(":") for x in out)):
                    break
    return out

async def main() -> None:
    eng = create_async_engine("postgresql+asyncpg://krama:krama-local-only@127.0.0.1:5433/krama_research")
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        for flavour in ["native", "starlette"]:
            rid = uuid.uuid4()
            async with eng.begin() as conn:
                await conn.execute(text("INSERT INTO runs(id, status) VALUES (:id, 'running')"), {"id": rid})
            for t in ["run.started", "step.started", "step.verified"]:
                await c.post(f"/runs/{rid}/emit/{t}")
            path = f"/{flavour}/runs/{rid}/events"
            print(f"[{flavour}]")
            print("  first connect, read 2   :", await read(c, path, None, 2, raw=True))
            # disconnect happened (we broke out). Emit more while nobody listens.
            for t in ["step.started", "step.verified"]:
                await c.post(f"/runs/{rid}/emit/{t}")
            print("  resume Last-Event-ID=2  :", await read(c, path, 2, 3))
            # live: emitter fires 300 ms after the client is waiting
            async def later() -> None:
                await asyncio.sleep(0.3); await c.post(f"/runs/{rid}/emit/run.finished")
            t0 = time.perf_counter()
            task = asyncio.create_task(later())
            got = await read(c, path, 5, 1)
            await task
            print(f"  live tail latency       : {got} in {(time.perf_counter()-t0)*1000:.0f} ms (300 ms was the emit delay)")
        # heartbeat while idle: sse-starlette ping=1 s; native fixed 15 s
        rid = uuid.uuid4()
        async with eng.begin() as conn:
            await conn.execute(text("INSERT INTO runs(id, status) VALUES (:id, 'running')"), {"id": rid})
        t0 = time.perf_counter()
        print("  starlette idle 2 lines  :", await read(c, f"/starlette/runs/{rid}/events", None, 2, raw=False) or "", f"{time.perf_counter()-t0:.1f}s")
        t0 = time.perf_counter()
        print("  native idle first ping  :", await read(c, f"/native/runs/{rid}/events", None, 1, raw=False) or "", f"{time.perf_counter()-t0:.1f}s")
        await asyncio.sleep(0.5)
        print("  generators closed after client disconnects:", (await c.get("/closed")).json())
    await eng.dispose()
asyncio.run(main())
