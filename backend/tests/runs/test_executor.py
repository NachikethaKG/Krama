"""InProcessExecutor end to end: real Postgres, real Chromium, real observer and verifier, a real local site.

No LLM: the plan is already approved and stored, as the API (#48) will leave it.
"""

import asyncio
import json
import os
import urllib.request
import uuid
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from playwright.async_api import Page
from pydantic import TypeAdapter
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import ScriptedStep
from app.contracts_gen.common_schema import Action, Target
from app.contracts_gen.events_schema import RunEvent
from app.db import PlanRow, RunRow, TaskRow, WorkflowRow, WorkflowStepRow
from app.db.repositories import event_payload, events_after
from app.observer import PageObserver
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.store import RunJob
from app.targets import TargetSetup
from app.verifier import LayeredVerifier
from app.verifier.task_check import TaskVerdict
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("stop_runs")]

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
    sessions: Sessions,
    site: str,
    steps: list[dict[str, Any]],
    status: str = "queued",
    prompt: str = "Create the item demo-item",
) -> UUID:
    async with sessions.begin() as s:
        task = TaskRow(prompt=prompt, target_url=site, status="planned")
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
    await finished(executor, run_id)


async def events(sessions: Sessions, run_id: UUID) -> list[dict[str, Any]]:
    async with sessions() as s:
        rows = await events_after(s, run_id)
    payloads = [event_payload(r) for r in rows]
    for p in payloads:
        EVENTS.validate_python(p)  # every stored event is a contract event
    return payloads


RUN_END_S = 120.0
"""How long a test waits for a run to end after its last answer: generous, because Chromium can take many
seconds to close on a busy laptop (#339). A run that really hangs still fails; `stop_runs` cleans it up."""


async def finished(executor: InProcessExecutor, run_id: UUID, timeout_s: float = RUN_END_S) -> None:
    await asyncio.wait_for(executor.wait(run_id), timeout=timeout_s)


async def until(check: Callable[[], Awaitable[bool]], what: str, timeout_s: float = 60) -> None:
    """Poll `check` every 50 ms; fail naming `what` if it never holds (not on a stale value later)."""
    for _ in range(int(timeout_s / 0.05)):
        if await check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"timed out after {timeout_s:g} s waiting for {what}")


async def until_paused(sessions: Sessions, run_id: UUID, timeout_s: float = 60) -> None:
    for _ in range(int(timeout_s / 0.05)):
        if (await run_row(sessions, run_id)).status == "paused":
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"run never paused: {(await run_row(sessions, run_id)).status}")


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
        assert workflow.confidence == 1.0
        assert workflow.viewport == {"width": 1280, "height": 800, "device_scale_factor": 1.0}
        assert workflow.recording_path and (tmp_path / workflow.recording_path).is_file()
        password = workflow.steps[2]
        assert password.sensitive and password.action == {"type": "fill", "value": "***"}
        assert workflow.steps[1].action["value"] == "demo-item"
        assert workflow.steps[0].verification["method"] == ["url", "aria"]
        assert workflow.steps[0].target["bbox"] is not None
        assert workflow.steps[0].target["scroll"] == {"x": 0, "y": 0}
        # Step text rewritten from what ran (#73); the password's value is never written out.
        assert [st.instruction_text for st in workflow.steps] == [
            "Click “New item”.",
            "Enter “demo-item” in “Item name”.",
            "Fill in “Password”.",
            "Select the “Add a README” checkbox.",
            "Click “Create item”.",
        ]
        # Each step's place in the rrweb recording (#83), so the tutorial player can replay it: ms since the
        # recording's first event, in step order, inside the recording.
        timings = [(st.start_ms, st.end_ms) for st in workflow.steps]
        assert all(start is not None and end is not None and 0 <= start <= end for start, end in timings)
        starts = [start for start, _ in timings if start is not None]
        assert starts == sorted(starts), timings
        recorded = json.loads((tmp_path / workflow.recording_path).read_text(encoding="utf-8"))
        length = max(e["timestamp"] for e in recorded) - min(e["timestamp"] for e in recorded)
        assert starts[-1] <= length, (timings, length)


async def test_steps_get_no_timing_without_a_readable_recording(tmp_path: Path) -> None:
    executor = InProcessExecutor(RunStore(None), environment(tmp_path))  # type: ignore[arg-type]
    rows = [WorkflowStepRow(seq=1, start_ms=1_000, end_ms=2_000)]

    executor._to_recording_offsets(rows, None)
    assert (rows[0].start_ms, rows[0].end_ms) == (None, None)

    (tmp_path / "rec.json").write_text('[{"type": 4, "timestamp": 400}, {"type": 2, "timestamp": 500}]')
    rows = [WorkflowStepRow(seq=1, start_ms=1_000, end_ms=2_000)]
    executor._to_recording_offsets(rows, str(tmp_path / "rec.json"))
    assert (rows[0].start_ms, rows[0].end_ms) == (600, 1_600)


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


async def test_a_failed_step_without_a_planner_pauses_for_the_human(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    wrong = [{**GOOD_PLAN["steps"][0], "expected_state": {"url_matches": "^/nowhere$"}}]
    run_id = await queued_run(sessions, site, wrong)
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, verify_timeout_s=0.5))

    await executor.submit(run_id)
    await until_paused(sessions, run_id)
    assert await executor.confirm(run_id, 1, "deny")
    await finished(executor, run_id)

    assert (await run_row(sessions, run_id)).status == "cancelled"
    stream = await events(sessions, run_id)
    assert [e["type"] for e in stream] == [
        "run.started", "step.started", "step.action_done", "step.failed", "run.replanning", "run.paused",
        "run.cancelled",
    ]  # fmt: skip
    assert stream[5]["reason"] == "recovery_exhausted"  # a click is never retried; no planner to replan
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
    await finished(executor, run_id)  # the browser closes at once

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
    await finished(executor, run_id)
    await executor.submit(run_id)  # after it finished: loads, sees "verified", does nothing
    await finished(executor, run_id)

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
    executor = InProcessExecutor(RunStore(sessions), env)
    await executor.submit(second)
    await until_paused(sessions, second)

    paused = (await events(sessions, second))[-1]
    assert (paused["reason"], paused["step_seq"]) == ("verification_unclear", 3)  # a human looks
    assert await executor.confirm(second, 3, "deny")
    await finished(executor, second)
    assert (await run_row(sessions, second)).status == "cancelled"
    async with sessions() as s:
        assert (
            await s.scalar(select(func.count()).select_from(WorkflowRow).where(WorkflowRow.run_id == second))
            == 0
        )


class ScriptedTaskCheck:
    """Answers the task check (#274) with a fixed verdict and keeps what it was asked."""

    def __init__(self, done: bool | None, missing: str = "") -> None:
        self.verdict = TaskVerdict(done=done, missing=missing)
        self.asked: list[tuple[str, list[str], str, str]] = []

    async def check(self, task: str, steps: Sequence[str], final_path: str, final_page: str) -> TaskVerdict:
        self.asked.append((task, list(steps), final_path, final_page))
        return self.verdict


async def test_a_run_whose_steps_miss_part_of_the_task_fails(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    # Every step verifies, but the task asked for more than the plan did (#274): no verified workflow.
    task = "Create the item demo-item and add a file notes.md to it"
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"], prompt=task)
    check = ScriptedTaskCheck(done=False, missing="the file notes.md was not added")

    await run_to_end(InProcessExecutor(RunStore(sessions), environment(tmp_path, task_check=check)), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "task_incomplete", "missing": "the file notes.md was not added"}
    assert "the file notes.md was not added" in run.error["message"]
    stream = await events(sessions, run_id)
    assert [e["type"] for e in stream][-2:] == ["step.verified", "run.failed"]
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(WorkflowRow)) == 0
    [(asked_task, steps, path, page)] = check.asked
    assert asked_task == task
    assert len(steps) == len(GOOD_PLAN["steps"]) and steps[-1] == "Click “Create item”."
    assert path == "/done" and "Item created" in page  # the page the run ended on


async def test_an_unsure_task_check_keeps_the_run_verified(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    # No answer (or an LLM error) must never fail a run whose steps all verified.
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    check = ScriptedTaskCheck(done=None, missing="task check unavailable")

    await run_to_end(InProcessExecutor(RunStore(sessions), environment(tmp_path, task_check=check)), run_id)

    assert (await run_row(sessions, run_id)).status == "verified"
    assert len(check.asked) == 1


async def test_a_target_without_a_usable_session_fails_before_step_one(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    # #87: no stored session (or an expired one) means "log in again", not a run that fails on a login wall.
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    no_session = TargetSetup(site="github", sign_in_problem="No stored github session. Log in once.")
    env = environment(tmp_path, target=lambda _job: no_session)

    await run_to_end(InProcessExecutor(RunStore(sessions), env), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "sign_in_required"}
    assert run.error["message"] == "No stored github session. Log in once."
    assert [e["type"] for e in await events(sessions, run_id)] == ["run.started", "run.failed"]


async def test_a_session_that_no_longer_signs_in_fails_on_the_first_page(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    async def signed_out(_page: Page) -> bool:
        return False

    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    dead = TargetSetup(
        site="github", storage_state={"cookies": [], "origins": []}, signed_in_check=signed_out
    )
    env = environment(tmp_path, target=lambda _job: dead)

    await run_to_end(InProcessExecutor(RunStore(sessions), env), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "sign_in_required"}
    assert [e["type"] for e in await events(sessions, run_id)] == ["run.started", "run.failed"]


async def test_a_site_that_cannot_be_opened_fails_the_run_clearly(sessions: Sessions, tmp_path: Path) -> None:
    # #89: github.com once didn't load within the timeout; that is "site unreachable", not a crash.
    run_id = await queued_run(sessions, "http://127.0.0.1:1", GOOD_PLAN["steps"])  # nothing listens there

    await run_to_end(InProcessExecutor(RunStore(sessions), environment(tmp_path)), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "site_unreachable"}
    assert "127.0.0.1:1" in run.error["message"]


async def test_a_slow_target_gets_longer_to_show_a_steps_effect(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    # #89: GitHub lists a new branch 3+ s after the click; the run's default re-check window ends sooner.
    slow = step(1, {"type": "navigate", "value": "/slow"}, {}, "Open it.", {"url_matches": "^/done$"})
    run_id = await queued_run(sessions, site, [slow])  # /slow moves on to /done after 600 ms
    env = environment(tmp_path, verify_timeout_s=0.1, target=lambda _job: TargetSetup(verify_timeout_s=5.0))

    await run_to_end(InProcessExecutor(RunStore(sessions), env), run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "verified", run.error
