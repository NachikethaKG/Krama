"""The migrations build exactly the tables the models describe, on a real Postgres."""

import asyncio
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
from app.db import Base
from app.db.models import (
    PLAN_STATUSES,
    RISKS,
    RUN_KINDS,
    RUN_STATUSES,
    TASK_STATUSES,
    VALIDATION_STATUSES,
    WORKFLOW_STATUSES,
    WORKFLOW_VERSION_SOURCES,
    WORKFLOW_VERSION_STATUSES,
)
from tests.conftest import alembic_config

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
        ("ck_runs_kind", RUN_KINDS),
        ("ck_workflows_status", WORKFLOW_STATUSES),
        ("ck_workflow_steps_risk", RISKS),
        ("ck_workflow_versions_source", WORKFLOW_VERSION_SOURCES),
        ("ck_workflow_versions_status", WORKFLOW_VERSION_STATUSES),
        ("ck_validations_status", VALIDATION_STATUSES),
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


BEFORE_VERSIONS = "01af9d382dac"
_OLD_ROWS = [
    "INSERT INTO tasks (id, prompt, target_url, status) VALUES"
    " ('00000000-0000-4000-8000-000000000001', 'p', 'http://127.0.0.1:3001', 'planned')",
    "INSERT INTO plans (id, task_id, risk, expected_result, steps) VALUES"
    " ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000001', 'low', 'r', '[]')",
    "INSERT INTO runs (id, plan_id, plan_revision, status) VALUES"
    " ('00000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-000000000002', 1, 'verified')",
    "INSERT INTO workflows (id, task_id, run_id, title, target_app, target_url, status, confidence,"
    " recording_path) VALUES ('00000000-0000-4000-8000-000000000004', '00000000-0000-4000-8000-000000000001',"
    " '00000000-0000-4000-8000-000000000003', 't', 'gitea', 'http://127.0.0.1:3001', 'verified', 0.5,"
    " 'r.json')",
    *[
        "INSERT INTO workflow_steps (workflow_id, id, seq, action, target, instruction_text, expected_state,"
        " observed_state, verification, risk) VALUES ('00000000-0000-4000-8000-000000000004',"
        f" '00000000-0000-4000-8000-00000000001{n}', {n}, '{{}}', '{{}}', 'x', '{{}}', '{{}}', '{{}}', 'low')"
        for n in (1, 2)
    ],
]


async def test_existing_workflows_become_their_version_1(
    sessions: async_sessionmaker[AsyncSession], test_db_url: str
) -> None:
    """The versions migration turns every stored workflow (and its steps) into a current version 1."""
    cfg = alembic_config(test_db_url)
    await asyncio.to_thread(command.downgrade, cfg, BEFORE_VERSIONS)
    try:
        async with sessions.begin() as s:
            for sql in _OLD_ROWS:
                await s.execute(text(sql))
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")

    async with sessions() as s:
        [version] = (await s.execute(text(
            "SELECT v.id, v.revision, v.source, v.status, v.confidence, v.recording_path, w.revision,"
            " v.id = w.current_version_id, v.run_id = w.run_id FROM workflow_versions v"
            " JOIN workflows w ON w.id = v.workflow_id"
        ))).all()  # fmt: skip
        assert tuple(version)[1:] == (1, "initial", "current", 0.5, "r.json", 1, True, True)
        steps = (await s.execute(text("SELECT version_id FROM workflow_steps"))).scalars().all()
        assert steps == [version.id, version.id]
