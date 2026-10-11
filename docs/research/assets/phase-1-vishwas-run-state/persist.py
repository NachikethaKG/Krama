"""Crash-safe run state on Postgres 16 with SQLAlchemy 2.1 async + asyncpg (Windows default loop).

Pattern under test: one transaction per transition =
  UPDATE runs SET status=:new, last_event_seq=last_event_seq+1 WHERE id=:id AND status=ANY(:allowed_from) RETURNING last_event_seq
  INSERT INTO run_events(run_id, seq, type, data) VALUES (:id, <returned seq>, ...)
"""
import asyncio, subprocess, sys, uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

URL = "postgresql+asyncpg://krama:krama-local-only@127.0.0.1:5433/krama_research"
DDL = [
    "DROP TABLE IF EXISTS run_events", "DROP TABLE IF EXISTS runs",
    """CREATE TABLE runs (id uuid PRIMARY KEY, status text NOT NULL
         CHECK (status IN ('queued','running','paused','verified','failed','cancelled')),
         last_event_seq int NOT NULL DEFAULT 0)""",
    """CREATE TABLE run_events (run_id uuid REFERENCES runs(id), seq int, type text NOT NULL,
         data jsonb NOT NULL DEFAULT '{}', ts timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (run_id, seq))""",
]
ALLOWED_FROM = {"running": ["queued", "paused"], "paused": ["running"], "cancelled": ["queued", "running", "paused"],
                "verified": ["running"], "failed": ["running", "paused"]}

async def transition(eng: AsyncEngine, run_id: uuid.UUID, new: str, crash_before_commit: bool = False) -> int | None:
    async with eng.begin() as c:  # commits on exit, rolls back on exception / lost connection
        seq = (await c.execute(text(
            "UPDATE runs SET status=:new, last_event_seq=last_event_seq+1 "
            "WHERE id=:id AND status = ANY(:src) RETURNING last_event_seq"),
            {"new": new, "id": run_id, "src": ALLOWED_FROM[new]})).scalar_one_or_none()
        if seq is None:
            return None  # someone else moved the run first, or the transition is illegal
        await c.execute(text("INSERT INTO run_events(run_id, seq, type, data) VALUES (:id, :seq, 'run.status', "
                             "jsonb_build_object('status', CAST(:new AS text)))"), {"id": run_id, "seq": seq, "new": new})
        if crash_before_commit:
            import os; os._exit(1)  # simulate the process dying mid-transaction
        return seq

async def append_event(eng: AsyncEngine, run_id: uuid.UUID, type_: str) -> int:
    async with eng.begin() as c:
        seq = (await c.execute(text("UPDATE runs SET last_event_seq=last_event_seq+1 WHERE id=:id RETURNING last_event_seq"),
                               {"id": run_id})).scalar_one()
        await c.execute(text("INSERT INTO run_events(run_id, seq, type) VALUES (:id, :seq, :t)"),
                        {"id": run_id, "seq": seq, "t": type_})
        return seq

async def state(eng: AsyncEngine, run_id: uuid.UUID) -> tuple[str, int, int]:
    async with eng.connect() as c:
        s, last = (await c.execute(text("SELECT status, last_event_seq FROM runs WHERE id=:id"), {"id": run_id})).one()
        n = (await c.execute(text("SELECT count(*) FROM run_events WHERE run_id=:id"), {"id": run_id})).scalar_one()
    return s, last, n

async def main() -> None:
    eng = create_async_engine(URL, pool_size=20)
    if sys.argv[1:] == ["crash"]:
        await transition(eng, uuid.UUID(sys.argv[0] if False else open("run_id.txt").read()), "running", crash_before_commit=True)
        return
    async with eng.begin() as c:
        for d in DDL:
            await c.execute(text(d))
    rid = uuid.uuid4()
    async with eng.begin() as c:
        await c.execute(text("INSERT INTO runs(id, status) VALUES (:id, 'queued')"), {"id": rid})

    # 1) crash mid-transaction in another process
    open("run_id.txt", "w").write(str(rid))
    rc = subprocess.run([sys.executable, __file__, "crash"]).returncode
    print("1) child exited with", rc, "-> state after crash:", await state(eng, rid))

    # 2) legal + illegal transitions
    print("2) queued->running seq:", await transition(eng, rid, "running"))
    print("   running->verified then verified->paused (illegal):", await transition(eng, rid, "verified"), await transition(eng, rid, "paused"))

    # 3) race: 20 concurrent 'cancel' vs 'pause' on a running run: exactly one wins
    rid2 = uuid.uuid4()
    async with eng.begin() as c:
        await c.execute(text("INSERT INTO runs(id, status) VALUES (:id, 'running')"), {"id": rid2})
    res = await asyncio.gather(*[transition(eng, rid2, "cancelled" if i % 2 else "verified") for i in range(20)])
    print("3) winners:", sum(r is not None for r in res), "| state:", await state(eng, rid2))

    # 4) 200 concurrent event appends on one run: gapless 1..N, no PK clash
    rid3 = uuid.uuid4()
    async with eng.begin() as c:
        await c.execute(text("INSERT INTO runs(id, status) VALUES (:id, 'running')"), {"id": rid3})
    seqs = await asyncio.gather(*[append_event(eng, rid3, "step.started") for _ in range(200)])
    print("4) appends:", len(seqs), "gapless:", sorted(seqs) == list(range(1, 201)))
    await eng.dispose()

asyncio.run(main())
