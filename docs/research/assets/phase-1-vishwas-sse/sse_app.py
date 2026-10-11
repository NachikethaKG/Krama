"""Two SSE endpoints over the same run_events table: FastAPI native vs sse-starlette.
Catch-up from Postgres after Last-Event-ID, then live tail: wait on an in-process asyncio.Condition (woken by the
writer) with a timeout, then re-query `seq > last` — the DB stays the source of truth, so no event is lost."""
import asyncio, json, uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from fastapi import FastAPI, Header, Request
from fastapi.sse import EventSourceResponse as NativeESR, ServerSentEvent as NativeSSE
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sse_starlette import EventSourceResponse as StarletteESR, ServerSentEvent as StarletteSSE

eng = create_async_engine("postgresql+asyncpg://krama:krama-local-only@127.0.0.1:5433/krama_research")
app = FastAPI()
wakeups: dict[uuid.UUID, asyncio.Condition] = defaultdict(asyncio.Condition)
closed: list[str] = []

async def events_after(run_id: uuid.UUID, last: int) -> list[tuple[int, str, dict]]:
    async with eng.connect() as c:
        rows = await c.execute(text("SELECT seq, type, data FROM run_events WHERE run_id=:r AND seq>:s ORDER BY seq"),
                               {"r": run_id, "s": last})
        return [(r.seq, r.type, r.data) for r in rows]

async def tail(run_id: uuid.UUID, last: int, who: str) -> AsyncIterator[tuple[int, str, dict]]:
    try:
        while True:
            for ev in await events_after(run_id, last):
                last = ev[0]
                yield ev
                if ev[1] == "run.finished":
                    return
            cond = wakeups[run_id]
            async with cond:
                try:
                    await asyncio.wait_for(cond.wait(), timeout=5)
                except TimeoutError:
                    pass
    finally:
        closed.append(who)  # proves the generator is cleaned up on client disconnect

@app.post("/runs/{run_id}/emit/{type_}")
async def emit(run_id: uuid.UUID, type_: str) -> dict[str, int]:
    async with eng.begin() as c:
        seq = (await c.execute(text("UPDATE runs SET last_event_seq=last_event_seq+1 WHERE id=:r RETURNING last_event_seq"), {"r": run_id})).scalar_one()
        await c.execute(text("INSERT INTO run_events(run_id, seq, type, data) VALUES (:r,:s,:t,'{}')"), {"r": run_id, "s": seq, "t": type_})
    cond = wakeups[run_id]
    async with cond:
        cond.notify_all()
    return {"seq": seq}

@app.get("/native/runs/{run_id}/events", response_class=NativeESR)
async def native(run_id: uuid.UUID, last_event_id: int = Header(0)) -> AsyncIterator[NativeSSE]:
    async for seq, type_, data in tail(run_id, last_event_id, "native"):
        yield NativeSSE(id=str(seq), event=type_, data=data)

@app.get("/starlette/runs/{run_id}/events")
async def starlette(run_id: uuid.UUID, request: Request, last_event_id: int = Header(0)) -> StarletteESR:
    async def gen() -> AsyncIterator[StarletteSSE]:
        async for seq, type_, data in tail(run_id, last_event_id, "starlette"):
            yield StarletteSSE(id=str(seq), event=type_, data=json.dumps(data))
    return StarletteESR(gen(), ping=1)

@app.get("/closed")
async def get_closed() -> list[str]:
    return closed
