"""Apply a v1 schema, then ask Alembic's compare_metadata about ONE edit at a time."""
import asyncio
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, DateTime, Enum, Index, MetaData, String, Table, Column, Integer, text, UniqueConstraint
from sqlalchemy.ext.asyncio import create_async_engine

URL = "postgresql+asyncpg://krama:krama-local-only@127.0.0.1:5433/krama_alembic"

def table(md: MetaData, *, status_len=20, default="0", check="('a','b')", col="browser_session",
          ts_tz=True, idx=False, enum_vals=("x", "y"), uniq=False, nullable=True) -> Table:
    args = [Column("id", Integer, primary_key=True),
            Column("status", String(status_len)),
            Column("retry_count", Integer, server_default=text(default)),
            Column(col, String, nullable=nullable),
            Column("ts", DateTime(timezone=ts_tz)),
            Column("kind", Enum(*enum_vals, name="kind_enum")),
            CheckConstraint(f"status IN {check}", name="ck_status")]
    if idx: args.append(Index("ix_status", "status"))
    if uniq: args.append(UniqueConstraint("status", name="uq_status"))
    return Table("probe", md, *args)

EDITS = {
    "column type length String(20)->String(50)": dict(status_len=50),
    "server default '0'->'1'": dict(default="1"),
    "CHECK constraint values": dict(check="('a','b','c')"),
    "column rename": dict(col="worker_id"),
    "timestamptz -> timestamp": dict(ts_tz=False),
    "add index": dict(idx=True),
    "add unique constraint": dict(uniq=True),
    "nullable -> NOT NULL": dict(nullable=False),
    "Postgres ENUM gains a value": dict(enum_vals=("x", "y", "z")),
}

async def main() -> None:
    eng = create_async_engine(URL)
    async with eng.begin() as c:
        await c.execute(text("DROP TABLE IF EXISTS probe")); await c.execute(text("DROP TYPE IF EXISTS kind_enum"))
        md = MetaData(); table(md); await c.run_sync(md.create_all)
    for name, kw in EDITS.items():
        md = MetaData(); table(md, **kw)
        async with eng.connect() as c:
            diff = await c.run_sync(lambda sc: compare_metadata(
                MigrationContext.configure(sc, opts={}), md))
        found = [d[0] if isinstance(d, tuple) else d[0][0] for d in diff] if diff else []
        print(f"{'DETECTED' if diff else 'MISSED  '}  {name:45} {found}")
    async with eng.begin() as c:
        await c.execute(text("DROP TABLE probe")); await c.execute(text("DROP TYPE kind_enum"))
    await eng.dispose()

asyncio.run(main())
