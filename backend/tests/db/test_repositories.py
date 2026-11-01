"""Repositories against a real Postgres: run transitions, events, plan revisions, workflows."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.contracts_gen.events_schema import RunEvent, RunStartedEvent
from app.db import (
    PlanRow,
    RunEventRow,
    RunRow,
    TaskRow,
    UserRow,
    WorkflowRow,
    WorkflowStepRow,
    WorkflowVersionRow,
)
from app.db.repositories import (
    InvalidRunEventError,
    add_workflow,
    add_workflow_version,
    append_event,
    decide_plan,
    event_payload,
    events_after,
    list_runs,
    list_versions,
    list_workflows,
    runs_with_status,
    transition_run,
    update_plan_steps,
)

pytestmark = pytest.mark.anyio

Sessions = async_sessionmaker[AsyncSession]
STEP: dict[str, Any] = {
    "seq": 1,
    "action": {"type": "click"},
    "target": {"role": "link", "name": "New Repository"},
    "instruction_text": "Click New Repository.",
    "expected_state": {"url_matches": "^/repo/create$"},
    "risk": "low",
}


async def new_user(sessions: Sessions) -> UserRow:
    async with sessions.begin() as s:
        user = UserRow(email=f"{uuid4().hex[:8]}@krama.test", password_hash="x")
        s.add(user)
    return user


async def new_run(sessions: Sessions, *, status: str = "queued", user: UserRow | None = None) -> RunRow:
    async with sessions.begin() as s:
        task = TaskRow(
            user_id=user.id if user else None,
            prompt="Create a repository",
            target_url="http://localhost:3001",
            status="planned",
        )
        s.add(task)
        await s.flush()
        plan = PlanRow(task_id=task.id, risk="low", expected_result="A repo page", steps=[STEP])
        s.add(plan)
        await s.flush()
        run = RunRow(plan_id=plan.id, plan_revision=plan.revision, status=status)
        s.add(run)
    return run


def started(run: RunRow) -> dict[str, Any]:
    return {"plan_id": str(run.plan_id), "total_steps": 1}


async def start(sessions: Sessions, run_id: UUID, plan_id: UUID) -> RunEventRow | None:
    async with sessions.begin() as s:
        return await transition_run(
            s,
            run_id,
            to="running",
            allowed_from=("queued",),
            event_type="run.started",
            event_data={"plan_id": str(plan_id), "total_steps": 1},
            started_at=datetime.now(UTC),
        )


async def get_run(sessions: Sessions, run_id: UUID) -> RunRow:
    async with sessions() as s:
        run = await s.get(RunRow, run_id)
        assert run is not None
        return run


# --- runs and events -----------------------------------------------------------------------------------


async def test_transition_moves_the_run_and_stores_a_contract_event(sessions: Sessions) -> None:
    run = await new_run(sessions)

    event = await start(sessions, run.id, run.plan_id)

    assert event is not None and event.seq == 1
    stored = await get_run(sessions, run.id)
    assert (stored.status, stored.last_event_seq) == ("running", 1)
    assert stored.started_at is not None and stored.started_at.tzinfo is not None
    parsed: RunEvent = TypeAdapter(RunEvent).validate_python(event_payload(event))
    assert isinstance(parsed, RunStartedEvent) and parsed.run_id == run.id


async def test_illegal_transition_writes_nothing(sessions: Sessions) -> None:
    run = await new_run(sessions, status="verified")

    assert await start(sessions, run.id, run.plan_id) is None

    stored = await get_run(sessions, run.id)
    assert (stored.status, stored.last_event_seq) == ("verified", 0)
    async with sessions() as s:
        assert await events_after(s, run.id) == []


async def test_unknown_run_is_not_an_error(sessions: Sessions) -> None:
    assert await start(sessions, uuid4(), uuid4()) is None


async def test_of_racing_transitions_exactly_one_wins(sessions: Sessions) -> None:
    run = await new_run(sessions, status="running")

    async def attempt(to: str, event_type: str, data: dict[str, Any]) -> bool:
        async with sessions.begin() as s:
            row = await transition_run(
                s, run.id, to=to, allowed_from=("running",), event_type=event_type, event_data=data
            )
            return row is not None

    cancel = ("cancelled", "run.cancelled", {"reason": "user"})
    fail = ("failed", "run.failed", {"error": {"code": "internal", "message": "boom"}})
    results = await asyncio.gather(*(attempt(*(cancel if i % 2 else fail)) for i in range(20)))

    assert sum(results) == 1
    async with sessions() as s:
        assert len(await events_after(s, run.id)) == 1


async def test_concurrent_events_get_gapless_seqs(sessions: Sessions) -> None:
    run = await new_run(sessions, status="running")

    async def add(i: int) -> None:
        async with sessions.begin() as s:
            data = {"step_seq": 1, "instruction_text": f"step {i}"}
            assert await append_event(s, run.id, "step.started", data) is not None

    await asyncio.gather(*(add(i) for i in range(100)))

    async with sessions() as s:
        seqs = [e.seq for e in await events_after(s, run.id)]
    assert seqs == list(range(1, 101))
    assert (await get_run(sessions, run.id)).last_event_seq == 100


async def test_events_after_resumes_from_last_event_id(sessions: Sessions) -> None:
    run = await new_run(sessions)
    await start(sessions, run.id, run.plan_id)
    for i in (1, 2):
        async with sessions.begin() as s:
            await append_event(s, run.id, "step.started", {"step_seq": i, "instruction_text": f"Step {i}"})

    async with sessions() as s:
        assert [e.seq for e in await events_after(s, run.id, 1)] == [2, 3]
        assert [e.seq for e in await events_after(s, run.id, 1, limit=1)] == [2]
        assert await events_after(s, run.id, 3) == []


async def test_an_event_that_breaks_the_contract_is_never_stored(sessions: Sessions) -> None:
    run = await new_run(sessions)

    with pytest.raises(InvalidRunEventError, match=r"run\.started"):
        async with sessions.begin() as s:
            await transition_run(
                s, run.id, to="running", allowed_from=("queued",), event_type="run.started", event_data={}
            )

    stored = await get_run(sessions, run.id)  # the status change rolled back with the event
    assert (stored.status, stored.last_event_seq) == ("queued", 0)


async def test_event_data_cannot_override_the_envelope(sessions: Sessions) -> None:
    run = await new_run(sessions)

    with pytest.raises(InvalidRunEventError, match="must not set"):
        async with sessions.begin() as s:
            await append_event(s, run.id, "run.cancelled", {"reason": "user", "seq": 99})


async def test_step_events_stop_once_the_run_is_cancelled(sessions: Sessions) -> None:
    run = await new_run(sessions, status="cancelled")

    async with sessions.begin() as s:
        row = await append_event(
            s, run.id, "step.started", {"step_seq": 1, "instruction_text": "x"}, while_status=("running",)
        )

    assert row is None
    assert (await get_run(sessions, run.id)).last_event_seq == 0


async def test_only_known_run_columns_can_change(sessions: Sessions) -> None:
    run = await new_run(sessions)

    with pytest.raises(ValueError, match="plan_id"):
        async with sessions.begin() as s:
            await transition_run(
                s, run.id, to="running", allowed_from=("queued",), event_type="run.started",
                event_data=started(run), plan_id=uuid4(),
            )  # fmt: skip


async def test_status_check_rejects_unknown_values(sessions: Sessions) -> None:
    run = await new_run(sessions)

    with pytest.raises(IntegrityError, match="ck_runs_status"):
        async with sessions.begin() as s:
            await transition_run(
                s, run.id, to="draft", allowed_from=("queued",), event_type="run.started",
                event_data=started(run),
            )  # fmt: skip


async def test_run_history_pages_newest_first(sessions: Sessions) -> None:
    owner, other = await new_user(sessions), await new_user(sessions)
    ids = []
    for _ in range(5):
        run = await new_run(sessions, user=owner)
        ids.append(run.id)
    async with sessions.begin() as s:  # distinct, known created_at values
        for i, run_id in enumerate(ids):
            row = await s.get(RunRow, run_id)
            assert row is not None
            row.created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=i)

    async with sessions() as s:
        first = await list_runs(s, user_id=owner.id, limit=2)
        second = await list_runs(s, user_id=owner.id, limit=2, before=(first[-1].created_at, first[-1].id))
        rest = await list_runs(s, user_id=owner.id, limit=2, before=(second[-1].created_at, second[-1].id))
        assert [r.id for r in [*first, *second, *rest]] == ids[::-1]
        assert await list_runs(s, user_id=other.id, limit=10) == []  # only your own runs (#94)
        assert await runs_with_status(s, ("queued",)) == ids


# --- plans ---------------------------------------------------------------------------------------------


async def test_plan_edits_need_the_current_revision(sessions: Sessions) -> None:
    run = await new_run(sessions)
    edited = [{**STEP, "instruction_text": "Open the New Repository page."}]

    async with sessions.begin() as s:
        plan = await update_plan_steps(s, run.plan_id, revision=1, steps=edited, risk="low")
        assert plan is not None and plan.revision == 2
    async with sessions.begin() as s:
        assert await update_plan_steps(s, run.plan_id, revision=1, steps=edited, risk="low") is None  # stale

    async with sessions.begin() as s:
        assert await decide_plan(s, run.plan_id, revision=1, to="approved") is None  # not what the user saw
        approved = await decide_plan(s, run.plan_id, revision=2, to="approved")
        assert approved is not None and approved.approved_at is not None
    async with sessions.begin() as s:
        assert await update_plan_steps(s, run.plan_id, revision=2, steps=edited, risk="low") is None
        assert await decide_plan(s, run.plan_id, revision=2, to="rejected") is None


async def test_decide_plan_only_approves_or_rejects(sessions: Sessions) -> None:
    async with sessions.begin() as s:
        with pytest.raises(ValueError, match="approved or rejected"):
            await decide_plan(s, uuid4(), revision=1, to="proposed")


# --- workflows ----------------------------------------------------------------------------------------


def step_row(seq: int) -> WorkflowStepRow:
    return WorkflowStepRow(
        seq=seq,
        action={"type": "click"},
        target={"role": "link", "name": "New Repository"},
        instruction_text="Click New Repository.",
        expected_state={"url_matches": "^/repo/create$"},
        observed_state={"url": "/repo/create"},
        verification={"result": "verified", "method": ["url"], "confidence": 1.0},
        risk="low",
    )


async def new_workflow(
    sessions: Sessions, app: str, steps: list[int], user: UserRow | None = None
) -> WorkflowRow:
    run = await new_run(sessions, status="verified", user=user)
    async with sessions.begin() as s:
        plan = await s.get(PlanRow, run.plan_id)
        assert plan is not None
        workflow = WorkflowRow(
            task_id=plan.task_id,
            run_id=run.id,
            user_id=user.id if user else None,
            title="Create a repository",
            target_app=app,
            target_url="http://localhost:3001",
            status="verified",
            confidence=1.0,
        )
        await add_workflow(s, workflow, [step_row(n) for n in steps])
    return workflow


async def test_workflow_and_its_steps_round_trip(sessions: Sessions) -> None:
    workflow = await new_workflow(sessions, "gitea", [2, 1])

    async with sessions() as s:
        loaded = await s.get(WorkflowRow, workflow.id)
        assert loaded is not None
        assert [st.seq for st in loaded.steps] == [1, 2]  # ordered by seq
        assert loaded.preconditions == {} and loaded.revision == 1
        assert loaded.steps[0].verification["method"] == ["url"]


async def test_step_seq_is_unique_per_version(sessions: Sessions) -> None:
    with pytest.raises(IntegrityError, match="uq_workflow_steps_version_id_seq"):
        await new_workflow(sessions, "gitea", [1, 1])


async def test_list_workflows_filters_by_app(sessions: Sessions) -> None:
    owner, other = await new_user(sessions), await new_user(sessions)
    gitea = await new_workflow(sessions, "gitea", [1], owner)
    await new_workflow(sessions, "github", [1], owner)

    async with sessions() as s:
        assert [w.id for w in await list_workflows(s, user_id=owner.id, limit=10, target_app="gitea")] == [
            gitea.id
        ]
        assert len(await list_workflows(s, user_id=owner.id, limit=10)) == 2
        assert await list_workflows(s, user_id=other.id, limit=10) == []  # only your own (#94)
        assert await s.scalar(select(func.count()).select_from(WorkflowStepRow)) == 2


async def add_version(sessions: Sessions, workflow: WorkflowRow, steps: list[int]) -> WorkflowVersionRow:
    """A healed version 2 that becomes current: what #112 will do."""
    async with sessions.begin() as s:
        first = await s.get(WorkflowVersionRow, workflow.current_version_id)
        assert first is not None
        first.status = "superseded"
        await s.flush()
        version = WorkflowVersionRow(
            workflow_id=workflow.id,
            revision=2,
            source="heal",
            status="current",
            parent_version_id=first.id,
            steps=[step_row(n) for n in steps],
        )
        for step in version.steps:
            step.workflow_id = workflow.id
        s.add(version)
        await s.flush()
        row = await s.get(WorkflowRow, workflow.id)
        assert row is not None
        row.current_version_id, row.revision = version.id, 2
    return version


async def test_a_new_workflow_is_its_own_version_1(sessions: Sessions) -> None:
    workflow = await new_workflow(sessions, "gitea", [1, 2])

    async with sessions() as s:
        [(version, step_count)] = await list_versions(s, workflow.id)
        assert (version.revision, version.source, version.status, step_count) == (1, "initial", "current", 2)
        assert version.id == workflow.current_version_id and version.run_id == workflow.run_id
        assert version.confidence == 1.0 and version.parent_version_id is None


async def test_a_workflow_shows_only_its_current_versions_steps(sessions: Sessions) -> None:
    workflow = await new_workflow(sessions, "gitea", [1, 2, 3])
    healed = await add_version(sessions, workflow, [1, 2])

    async with sessions() as s:
        loaded = await s.get(WorkflowRow, workflow.id)
        assert loaded is not None
        assert loaded.revision == 2 and [st.seq for st in loaded.steps] == [1, 2]
        assert {st.version_id for st in loaded.steps} == {healed.id}
        versions = await list_versions(s, workflow.id)
        assert [(v.revision, v.status, n) for v, n in versions] == [(2, "current", 2), (1, "superseded", 3)]


async def test_a_workflow_has_at_most_one_current_version(sessions: Sessions) -> None:
    workflow = await new_workflow(sessions, "gitea", [1])

    with pytest.raises(IntegrityError, match="ix_workflow_versions_one_current"):
        async with sessions.begin() as s:
            s.add(WorkflowVersionRow(workflow_id=workflow.id, revision=2, source="heal", status="current"))


async def test_deleting_a_workflow_deletes_its_versions_and_steps(sessions: Sessions) -> None:
    workflow = await new_workflow(sessions, "gitea", [1, 2])
    await add_version(sessions, workflow, [1])

    async with sessions.begin() as s:
        await s.execute(delete(WorkflowRow).where(WorkflowRow.id == workflow.id))
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(WorkflowVersionRow)) == 0
        assert await s.scalar(select(func.count()).select_from(WorkflowStepRow)) == 0


async def test_a_published_heal_becomes_the_current_version(sessions: Sessions) -> None:
    workflow = await new_workflow(sessions, "gitea", [1, 2])
    async with sessions.begin() as s:
        row = await s.get(WorkflowRow, workflow.id)
        assert row is not None
        version = await add_workflow_version(
            s, row, [step_row(1), step_row(2)], source="heal", status="current", run_id=None, confidence=0.9,
            recording_path="runs/x/rrweb.json", viewport={"width": 1280, "height": 800}, change_summary=None,
        )  # fmt: skip

    async with sessions() as s:
        loaded = await s.get(WorkflowRow, workflow.id)
        assert loaded is not None
        assert (loaded.revision, loaded.current_version_id, loaded.status) == (2, version.id, "verified")
        assert loaded.recording_path == "runs/x/rrweb.json" and loaded.confidence == pytest.approx(0.9)
        assert {st.version_id for st in loaded.steps} == {version.id}
        versions = [
            (v.revision, v.status, v.parent_version_id) for v, _ in await list_versions(s, workflow.id)
        ]
        assert versions == [(2, "current", workflow.current_version_id), (1, "superseded", None)]


async def test_a_heal_for_review_leaves_the_current_version_and_marks_the_workflow_outdated(
    sessions: Sessions,
) -> None:
    workflow = await new_workflow(sessions, "gitea", [1, 2])
    async with sessions.begin() as s:
        row = await s.get(WorkflowRow, workflow.id)
        assert row is not None
        await add_workflow_version(
            s, row, [step_row(1)], source="heal", status="pending_review", run_id=None, confidence=0.9,
            recording_path="runs/y/rrweb.json", viewport=None, change_summary=None,
        )  # fmt: skip

    async with sessions() as s:
        loaded = await s.get(WorkflowRow, workflow.id)
        assert loaded is not None
        assert (loaded.revision, loaded.current_version_id, loaded.status) == (
            1,
            workflow.current_version_id,
            "outdated",
        )
        assert [st.seq for st in loaded.steps] == [
            1,
            2,
        ] and loaded.recording_path is None  # still version 1's
        assert [(v.revision, v.status) for v, _ in await list_versions(s, workflow.id)] == [
            (2, "pending_review"),
            (1, "current"),
        ]
