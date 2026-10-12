"""The migrations build exactly the tables the models describe, on a real Postgres."""

from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
from app.db import Base
from app.db.models import PLAN_STATUSES, RISKS, RUN_STATUSES, TASK_STATUSES, WORKFLOW_STATUSES
from tests.db.conftest import alembic_config

pytestmark = pytest.mark.anyio

PHASE_1_TABLES = {"tasks", "plans", "runs", "run_events", "workflows", "workflow_steps"}


async def _scalars(sessions: async_sessionmaker[AsyncSession], sql: str) -> list[Any]:
    async with sessions() as session:
        return list((await session.execute(text(sql))).scalars())


async def test_upgrade_head_creates_the_phase_1_tables(sessions: async_sessionmaker[AsyncSession]) -> None:
    tables = await _scalars(sessions, "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")

    assert set(tables) >= PHASE_1_TABLES


async def test_every_timestamp_is_timestamptz(sessions: async_sessionmaker[AsyncSession]) -> None:
    naive = await _scalars(
        sessions,
        "SELECT table_name || '.' || column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND data_type = 'timestamp without time zone'",
    )

    assert naive == []


async def test_models_and_migrations_have_not_drifted(sessions: async_sessionmaker[AsyncSession]) -> None:
    def diff(conn: Connection) -> list[Any]:
        context = MigrationContext.configure(conn, opts={"compare_server_default": True})
        return list(compare_metadata(context, Base.metadata))

    async with sessions() as session:
        conn = await session.connection()
        changes = await conn.run_sync(diff)

    assert changes == [], "models changed without a migration: run `uv run alembic revision --autogenerate`"


@pytest.mark.parametrize(
    ("constraint", "values"),
    [
        ("ck_tasks_status", TASK_STATUSES),
        ("ck_plans_status", PLAN_STATUSES),
        ("ck_plans_risk", RISKS),
        ("ck_runs_status", RUN_STATUSES),
        ("ck_workflows_status", WORKFLOW_STATUSES),
        ("ck_workflow_steps_risk", RISKS),
    ],
)
async def test_status_checks_match_the_contract(
    sessions: async_sessionmaker[AsyncSession], constraint: str, values: tuple[str, ...]
) -> None:
    """Autogenerate can't see a changed CHECK, so this catches a contract status with no migration."""
    [definition] = await _scalars(
        sessions, f"SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = '{constraint}'"
    )

    in_db = {part.split("'")[1] for part in definition.split("::text")[:-1]}
    assert in_db == set(values), definition


def test_downgrade_and_upgrade_again(test_db_url: str) -> None:
    cfg = alembic_config(test_db_url)

    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
