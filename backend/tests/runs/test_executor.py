"""InProcessExecutor end to end: real Postgres, real Chromium, real observer and verifier, a real local site.

No LLM: the plan is already approved and stored, as the API (#48) will leave it.
"""

import asyncio
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import TypeAdapter
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import ScriptedStep
from app.contracts_gen.common_schema import Action, Target
from app.contracts_gen.events_schema import RunEvent
from app.db import PlanRow, RunRow, TaskRow, WorkflowRow
from app.db.repositories import event_payload, events_after
from app.observer import PageObserver
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.store import RunJob
from app.verifier import LayeredVerifier
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = pytest.mark.anyio

Sessions = async_sessionmaker[AsyncSession]
EVENTS: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)
PASSWORD = {"role": "textbox", "name": "Password"}
# GOOD_PLAN plus a password: its value must never be stored.
PLAN = [
    *GOOD_PLAN["steps"][:2],
    step(
        3,
        {"type": "fill", "value": "s3cret-value"},
        PASSWORD,
        "Type the password.",
        {"field_values": [{**PASSWORD, "value": "s3cret-value"}]},
    ),
    *[{**s, "seq": s["seq"] + 1} for s in GOOD_PLAN["steps"][2:]],
]


async def queued_run(
    sessions: Sessions, site: str, steps: list[dict[str, Any]], status: str = "queued"
) -> UUID:
    async with sessions.begin() as s:
        task = TaskRow(prompt="Create the item demo-item", target_url=site, status="planned")
        s.add(task)
        await s.flush()
        plan = PlanRow(task_id=task.id, status="approved", risk="low", expected_result="done", steps=steps)
        s.add(plan)
        await s.flush()
        run = RunRow(plan_id=plan.id, plan_revision=1, status=status)
        s.add(run)
        await s.flush()
        return run.id


def environment(tmp_path: Path, **kw: Any) -> RunEnvironment:
    return RunEnvironment(
        verifier=LayeredVerifier(),
        observer_for=lambda run_id: PageObserver(artifacts_dir=tmp_path / "runs" / str(run_id)),
        artifacts_dir=tmp_path,
        **kw,
    )


async def run_to_end(executor: InProcessExecutor, run_id: UUID) -> None:
    await executor.submit(run_id)
    await asyncio.wait_for(executor.wait(run_id), timeout=120)


async def events(sessions: Sessions, run_id: UUID) -> list[dict[str, Any]]:
    async with sessions() as s:
        rows = await events_after(s, run_id)
    payloads = [event_payload(r) for r in rows]
    for p in payloads:
        EVENTS.validate_python(p)  # every stored event is a contract event
    return payloads


async def run_row(sessions: Sessions, run_id: UUID) -> RunRow:
    async with sessions() as s:
        row = await s.get(RunRow, run_id)
        assert row is not None
        return row


async def test_approved_plan_runs_to_a_stored_verified_workflow(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    run_id = await queued_run(sessions, site, PLAN)

    await run_to_end(InProcessExecutor(RunStore(sessions), environment(tmp_path)), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "verified", run.error
    assert run.started_at and run.finished_at and run.duration_ms and run.current_seq == 5
    stream = await events(sessions, run_id)
    assert [e["type"] for e in stream] == [
        "run.started",
        *["step.started", "step.action_done", "step.verified"] * 5,
        "run.completed",
    ]
    assert [e["seq"] for e in stream] == list(range(1, 18))
    assert stream[0]["total_steps"] == 5
    shot = stream[2]["screenshot_url"]
    assert (
        shot.startswith("/api/v1/artifacts/runs/")
        and (tmp_path / shot.removeprefix("/api/v1/artifacts/")).is_file()
    )

    async with sessions() as s:
        workflow = await s.get(WorkflowRow, UUID(stream[-1]["workflow_id"]))
        assert workflow is not None and workflow.run_id == run_id and workflow.status == "verified"
        assert [st.seq for st in workflow.steps] == [1, 2, 3, 4, 5]
        assert workflow.confidence == 1.0 and workflow.viewport == {"width": 1280, "height": 800}
        assert workflow.recording_path and (tmp_path / workflow.recording_path).is_file()
        password = workflow.steps[2]
        assert password.sensitive and password.action == {"type": "fill", "value": "***"}
        assert workflow.steps[1].action["value"] == "demo-item"
        assert workflow.steps[0].verification["method"] == ["url", "aria"]
        assert workflow.steps[0].target["bbox"] is not None


async def test_the_password_is_in_no_row_the_executor_writes(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    run_id = await queued_run(sessions, site, PLAN)

    await run_to_end(InProcessExecutor(RunStore(sessions), environment(tmp_path)), run_id)

    async with sessions() as s:
        stored = await s.scalar(text(ALL_EXECUTOR_ROWS))
    assert stored and "demo-item" in stored  # the check can see stored values at all
    assert "s3cret-value" not in stored


# Everything the executor writes, as one text blob. (`plans` is written by the API from the user's input.)
ALL_EXECUTOR_ROWS = """
    SELECT string_agg(j::text, '') FROM (
        SELECT to_jsonb(r) AS j FROM runs r
        UNION ALL SELECT to_jsonb(e) FROM run_events e
        UNION ALL SELECT to_jsonb(w) FROM workflows w
        UNION ALL SELECT to_jsonb(st) FROM workflow_steps st
    ) x
"""


async def test_a_step_that_does_not_verify_fails_the_run(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    wrong = [{**GOOD_PLAN["steps"][0], "expected_state": {"url_matches": "^/nowhere$"}}]
    run_id = await queued_run(sessions, site, wrong)
    env = environment(tmp_path, verify_timeout_s=0.5)

    await run_to_end(InProcessExecutor(RunStore(sessions), env), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed"
    assert run.error is not None and run.error["details"] == {"reason": "step_not_verified", "step_seq": 1}
    stream = await events(sessions, run_id)
    assert [e["type"] for e in stream] == [
        "run.started", "step.started", "step.action_done", "step.failed", "run.failed",
    ]  # fmt: skip
    assert stream[3]["expected"] == {"url_matches": "^/nowhere$"} and stream[3]["observed"]["url"] == "/form"
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(WorkflowRow)) == 0  # never a workflow


async def test_cancel_stops_a_running_run_at_its_step(sessions: Sessions, site: str, tmp_path: Path) -> None:
    never = step(
        2, {"type": "wait"}, {"role": "button", "name": "Never appears"}, "Wait.", {"url_matches": "/"}
    )
    run_id = await queued_run(sessions, site, [GOOD_PLAN["steps"][0], never])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))
    await executor.submit(run_id)
    for _ in range(200):  # until step 2 has started
        if (await run_row(sessions, run_id)).current_seq == 2:
            break
        await asyncio.sleep(0.05)

    assert await executor.cancel(run_id)
    await asyncio.wait_for(executor.wait(run_id), timeout=5)  # the browser closes at once

    run = await run_row(sessions, run_id)
    assert run.status == "cancelled" and run.finished_at is not None
    stream = await events(sessions, run_id)
    assert stream[-1]["type"] == "run.cancelled"
    assert (stream[-1]["reason"], stream[-1]["step_seq"]) == ("user", 2)
    assert not await executor.cancel(run_id)  # already finished


async def test_a_queued_run_cancelled_before_it_starts_never_opens_a_browser(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    run_id = await queued_run(sessions, site, PLAN)
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))

    assert await executor.cancel(run_id)
    await run_to_end(executor, run_id)

    stream = await events(sessions, run_id)
    assert [e["type"] for e in stream] == ["run.cancelled"]
    assert "step_seq" not in stream[0]


async def test_runs_wait_for_a_free_slot(sessions: Sessions, site: str, tmp_path: Path) -> None:
    first = await queued_run(sessions, site, GOOD_PLAN["steps"][:2])
    second = await queued_run(sessions, site, GOOD_PLAN["steps"][:2])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path), max_concurrent=1)

    await executor.submit(first)
    await executor.submit(second)
    await asyncio.wait_for(asyncio.gather(executor.wait(first), executor.wait(second)), timeout=120)

    a, b = await run_row(sessions, first), await run_row(sessions, second)
    assert a.status == b.status == "verified"
    assert a.finished_at and b.started_at and b.started_at >= a.finished_at  # never two browsers at once


async def test_recover_fails_every_run_a_restart_left_without_a_browser(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    running = await queued_run(sessions, site, PLAN, status="running")
    queued = await queued_run(sessions, site, PLAN, status="queued")
    paused = await queued_run(sessions, site, PLAN, status="paused")
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))

    assert sorted(await executor.recover()) == sorted([running, queued, paused])

    for run_id in (running, queued, paused):
        run = await run_row(sessions, run_id)
        assert run.status == "failed" and run.error is not None
        assert run.error["details"]["reason"] == "interrupted"
        assert (await events(sessions, run_id))[-1]["type"] == "run.failed"


async def test_a_failed_precondition_fails_the_run_before_step_one(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    def bad_login(_job: RunJob) -> list[ScriptedStep]:
        return [ScriptedStep(action=Action(type="click"), target=Target(role="button", name="Sign In"))]

    run_id = await queued_run(sessions, site, PLAN)
    env = environment(tmp_path, preconditions=bad_login)

    await run_to_end(InProcessExecutor(RunStore(sessions), env), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"]["reason"] == "precondition_failed"
    assert [e["type"] for e in await events(sessions, run_id)] == ["run.started", "run.failed"]


async def test_a_run_submitted_twice_runs_once(sessions: Sessions, site: str, tmp_path: Path) -> None:
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"][:1])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))

    await executor.submit(run_id)
    await executor.submit(run_id)
    await asyncio.wait_for(executor.wait(run_id), timeout=60)
    await executor.submit(run_id)  # after it finished: loads, sees "verified", does nothing
    await asyncio.wait_for(executor.wait(run_id), timeout=60)

    starts = [e for e in await events(sessions, run_id) if e["type"] == "run.started"]
    assert len(starts) == 1


GITEA = os.environ.get("GITEA_URL", "http://localhost:3001")


def _gitea_up() -> bool:
    try:
        with urllib.request.urlopen(f"{GITEA}/api/healthz", timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _gitea_up(), reason=f"Gitea not reachable at {GITEA}; start it with `just up`")
async def test_create_a_repository_on_real_gitea(sessions: Sessions, tmp_path: Path) -> None:
    from app.config import get_settings

    settings = get_settings()
    name = f"krama-run-{uuid.uuid4().hex[:8]}"
    repo_name = {"role": "textbox", "name": "Repository Name"}
    plan = [
        step(1, {"type": "navigate", "value": "/repo/create"}, {}, "Open the new repository form.",
             {"url_matches": "^/repo/create$"}),
        step(2, {"type": "fill", "value": name}, repo_name, "Type the repository name.",
             {"field_values": [{**repo_name, "value": name}]}),
        step(3, {"type": "click"}, {"role": "button", "name": "Create Repository"}, "Click Create.",
             {"url_matches": f"^/{settings.gitea_demo_user}/{name}$"}),
    ]  # fmt: skip
    run_id = await queued_run(sessions, GITEA, plan)
    env = environment(
        tmp_path,
        preconditions=lambda _job: login_steps(
            user=settings.gitea_demo_user, password=settings.gitea_demo_password
        ),
    )

    await run_to_end(InProcessExecutor(RunStore(sessions), env), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "verified", run.error
    # Independent check through Gitea's API, not through our own verifier.
    url = f"{GITEA}/api/v1/repos/{settings.gitea_demo_user}/{name}"
    assert await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=5).status) == 200
    async with sessions() as s:
        stored = await s.scalar(text(ALL_EXECUTOR_ROWS))
    assert settings.gitea_demo_password not in (stored or "")  # the login never reaches the database


@pytest.mark.skipif(not _gitea_up(), reason=f"Gitea not reachable at {GITEA}; start it with `just up`")
async def test_a_duplicate_create_on_real_gitea_never_verifies(sessions: Sessions, tmp_path: Path) -> None:
    """The research case: every action works, Gitea shows "name already used", nothing is created."""
    from app.config import get_settings

    settings = get_settings()
    name = f"krama-dup-{uuid.uuid4().hex[:8]}"
    repo_name = {"role": "textbox", "name": "Repository Name"}
    env = environment(
        tmp_path,
        preconditions=lambda _job: login_steps(
            user=settings.gitea_demo_user, password=settings.gitea_demo_password
        ),
        verify_timeout_s=1.0,
    )

    def plan(create_expects: dict[str, Any]) -> list[dict[str, Any]]:
        create = {"role": "button", "name": "Create Repository"}
        return [
            step(1, {"type": "navigate", "value": "/repo/create"}, {}, "Open.",
                 {"url_matches": "^/repo/create$"}),
            step(2, {"type": "fill", "value": name}, repo_name, "Type the name.",
                 {"field_values": [{**repo_name, "value": name}]}),
            step(3, {"type": "click"}, create, "Click Create.", create_expects),
        ]  # fmt: skip

    first = await queued_run(sessions, GITEA, plan({"url_matches": f"^/{settings.gitea_demo_user}/{name}$"}))
    await run_to_end(InProcessExecutor(RunStore(sessions), env), first)
    assert (await run_row(sessions, first)).status == "verified"

    # Same name again, with the weak expectations the old verifier accepted.
    weak = {"visible": [{"role": "button", "name": "Create Repository"}], "title_contains": "Gitea"}
    second = await queued_run(sessions, GITEA, plan(weak))
    await run_to_end(InProcessExecutor(RunStore(sessions), env), second)

    run = await run_row(sessions, second)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "verification_unclear", "step_seq": 3}
    async with sessions() as s:
        assert (
            await s.scalar(select(func.count()).select_from(WorkflowRow).where(WorkflowRow.run_id == second))
            == 0
        )
