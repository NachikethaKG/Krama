"""\"Do it for me\" (#129, #401) end to end: GET /workflows/{id}/inputs and POST /workflows/{id}/run, with the
real executor (Postgres, Chromium, observer, verifier) on the local test site and the fake LLM."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select, update

from app.agent.runlog import MASK
from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.run_schema import Run
from app.contracts_gen.workflow_schema import WorkflowInputList
from app.db import RunRow, ValidationRow, WorkflowRow, WorkflowVersionRow
from app.runs.executor import InProcessExecutor
from app.runs.validation_backend import RunValidationBackend
from app.targets import TargetSetup
from app.verifier import LayeredVerifier
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.api.test_reverify import change_step, verified_workflow, workflow_count
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio


async def do_it(api: Api, workflow_id: UUID, value: str = "team-notes") -> tuple[Run, list[dict[str, Any]]]:
    inputs = WorkflowInputList.model_validate(
        (await api.client.get(f"/workflows/{workflow_id}/inputs")).json()
    )
    body = {"revision": inputs.revision, "inputs": {inputs.inputs[0].key: value}}
    started = await api.client.post(f"/workflows/{workflow_id}/run", json=body)
    assert started.status_code == 202, started.text
    run = Run.model_validate(started.json())
    stream = await api.events(run.id)
    return Run.model_validate((await api.client.get(f"/runs/{run.id}")).json()), stream


async def test_the_inputs_are_the_typed_values_with_the_signed_in_account(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        api.svc.target = lambda _url: TargetSetup(signed_in_as="demo")

        got = await api.client.get(f"/workflows/{workflow_id}/inputs")

    assert got.status_code == 200, got.text
    inputs = WorkflowInputList.model_validate(got.json())
    assert (inputs.workflow_id, inputs.revision, inputs.account) == (workflow_id, 1, "demo")
    [only] = inputs.inputs
    assert (only.example, only.steps, only.min_length) == ("demo-item", [2], 3)


async def test_the_workflow_runs_with_the_users_value_and_stores_nothing(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        before = await workflow_count(sessions)
        resets: list[Sequence[Any]] = []

        async def reset(steps: Sequence[Any]) -> list[str]:
            resets.append(steps)
            return []

        api.svc.target = lambda _url: TargetSetup(reset=reset)

        run, stream = await do_it(api, workflow_id)

        assert (run.kind, run.source_workflow_id, run.status, run.workflow_id) == (
            "do_it", workflow_id, "verified", None
        )  # fmt: skip
        assert [e["type"] for e in stream] == [
            "run.started",
            *["step.started", "step.action_done", "step.verified"] * 4,
            "run.completed",
        ]
        assert stream[-1]["workflow_id"] == str(workflow_id)
        plan = Plan.model_validate((await api.client.get(f"/plans/{run.plan_id}")).json())
        assert plan.status == "approved"
        assert plan.steps[1].action.value == "team-notes"
        assert plan.steps[1].expected_state.field_values[0].value == "team-notes"  # type: ignore[index]
    assert resets == []  # never reset the user's site (P8)
    assert await workflow_count(sessions) == before
    assert not (tmp_path / "runs" / str(run.id) / "recording.json").exists()  # no rrweb recording (P14)


async def test_a_risky_step_pauses_for_the_user(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 4, risk="high")
        run_id = await start(api, workflow_id)

        paused = await wait_status(api, run_id, "paused")
        assert paused.current_seq == 4
        confirmed = await api.client.post(
            f"/runs/{run_id}/confirm", json={"step_seq": 4, "decision": "allow"}
        )
        assert confirmed.status_code == 200, confirmed.text
        stream = await api.events(run_id)

    pause = next(e for e in stream if e["type"] == "run.paused")
    assert (pause["reason"], pause["step_seq"]) == ("destructive_action", 4)
    assert stream[-1]["type"] == "run.completed"


async def test_a_failed_step_ends_the_run_without_replanning(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    # The planner would answer a replan; a do-it run must never ask it (P7, P10).
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN), reply(GOOD_PLAN, name="replan"))) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 4, target={"role": "button", "name": "Gone"})

        run, stream = await do_it(api, workflow_id)

    assert run.status == "failed"
    assert run.error is not None and run.error.details["reason"] == "locator_miss"  # type: ignore[index]
    assert run.error.message.startswith("Step 4 failed")
    types = [e["type"] for e in stream]
    assert "run.replanning" not in types and "run.paused" not in types
    assert types.count("step.failed") == 1  # a click is never retried; no heal, no second try


async def test_an_undecided_step_pauses_instead_of_asking_vision(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    class NoVision:
        async def judge(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("a do-it run never asks the vision judge")

    svc = services(sessions, tmp_path, reply(GOOD_PLAN), verifier=LayeredVerifier(NoVision()))
    async with Api(svc) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 3, expected_state={})  # nothing the cheap checks can see

        run_id = await start(api, workflow_id)
        await wait_status(api, run_id, "paused")
        await api.client.post(f"/runs/{run_id}/cancel")
        stream = await api.events(run_id)

    pause = next(e for e in stream if e["type"] == "run.paused")
    assert (pause["reason"], pause["step_seq"]) == ("verification_unclear", 3)


@pytest.mark.parametrize(
    ("change", "status", "reason"),
    [
        ("outdated", 409, "not_verified"),
        ("pending_review", 409, "pending_review"),
        ("secret", 409, "secret_not_stored"),
    ],
)
async def test_workflows_that_cant_run_are_refused(
    sessions: Sessions, tmp_path: Path, site: str, change: str, status: int, reason: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        async with sessions.begin() as s:
            if change == "outdated":
                await s.execute(
                    update(WorkflowRow).where(WorkflowRow.id == workflow_id).values(status="outdated")
                )
            if change == "pending_review":
                workflow = await s.get(WorkflowRow, workflow_id)
                assert workflow is not None
                s.add(
                    WorkflowVersionRow(
                        workflow_id=workflow_id, revision=2, source="heal", status="pending_review",
                        parent_version_id=workflow.current_version_id,
                    )
                )  # fmt: skip
        if change == "secret":
            await change_step(
                sessions, workflow_id, 2, sensitive=True, action={"type": "fill", "value": MASK}
            )

        got = await api.client.get(f"/workflows/{workflow_id}/inputs")
        ran = await api.client.post(f"/workflows/{workflow_id}/run", json={"revision": 1, "inputs": {}})

    for response in (got, ran):
        assert response.status_code == status, response.text
        assert response.json()["error"]["details"]["reason"] == reason


@pytest.mark.parametrize(
    ("body", "status", "details"),
    [
        ({"revision": 1, "inputs": {"item_name": "ab"}}, 422, {"reason": "input_unsafe", "key": "item_name"}),
        (
            {"revision": 1, "inputs": {"item_name": "team notes"}},
            422,
            {"reason": "input_unsafe", "key": "item_name"},
        ),
        ({"revision": 1, "inputs": {}}, 422, {"reason": "input_unsafe", "key": "item_name"}),
        (
            {"revision": 1, "inputs": {"item_name": "ok-1", "x": "y"}},
            422,
            {"reason": "input_unsafe", "key": "x"},
        ),
        ({"revision": 2, "inputs": {"item_name": "team-notes"}}, 409, {"reason": "stale_revision"}),
    ],
)
async def test_bad_requests_are_refused_before_anything_runs(
    sessions: Sessions, tmp_path: Path, site: str, body: dict[str, Any], status: int, details: dict[str, Any]
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        runs_before = await run_count(sessions)

        ran = await api.client.post(f"/workflows/{workflow_id}/run", json=body)

    assert ran.status_code == status, ran.text
    assert ran.json()["error"]["details"] == details
    assert await run_count(sessions) == runs_before


async def test_only_the_owner_can_see_or_run_it(sessions: Sessions, tmp_path: Path, site: str) -> None:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN))
    async with Api(svc) as api:
        workflow_id = await verified_workflow(api, site)
    async with Api(svc, await make_user(sessions)) as other:
        got = await other.client.get(f"/workflows/{workflow_id}/inputs")
        ran = await other.client.post(f"/workflows/{workflow_id}/run", json={"revision": 1, "inputs": {}})

    assert got.status_code == ran.status_code == 404


async def test_a_failed_do_it_run_makes_the_workflow_due_for_validation(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        validated = datetime.now(UTC) - timedelta(hours=1)
        async with sessions.begin() as s:
            s.add(ValidationRow(workflow_id=workflow_id, status="passed", ran_at=validated))
        assert isinstance(api.svc.executor, InProcessExecutor)
        backend = RunValidationBackend(sessions, api.svc.executor, lambda _url: TargetSetup())

        assert await last_validated(backend, workflow_id) == validated
        async with sessions.begin() as s:
            s.add(failed_do_it_run(workflow_id, await any_plan_id(sessions, workflow_id)))

        assert await last_validated(backend, workflow_id) is None  # due at the next pass (P9)


# --- helpers


async def start(api: Api, workflow_id: UUID) -> UUID:
    inputs = WorkflowInputList.model_validate(
        (await api.client.get(f"/workflows/{workflow_id}/inputs")).json()
    )
    body = {"revision": inputs.revision, "inputs": {"item_name": "team-notes"}}
    started = await api.client.post(f"/workflows/{workflow_id}/run", json=body)
    assert started.status_code == 202, started.text
    return Run.model_validate(started.json()).id


async def wait_status(api: Api, run_id: UUID, status: str) -> Run:
    for _ in range(400):
        run = Run.model_validate((await api.client.get(f"/runs/{run_id}")).json())
        if run.status == status:
            return run
        await asyncio.sleep(0.05)
    raise AssertionError(f"run {run_id} never became {status}: {run.status}")


async def run_count(sessions: Sessions) -> int:
    async with sessions() as s:
        return int((await s.execute(select(func.count()).select_from(RunRow))).scalar_one())


async def last_validated(backend: RunValidationBackend, workflow_id: UUID) -> datetime | None:
    [candidate] = [c for c in await backend.candidates() if c.workflow_id == workflow_id]
    return candidate.last_validated_at


async def any_plan_id(sessions: Sessions, workflow_id: UUID) -> UUID:
    async with sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None
        run = await s.get(RunRow, workflow.run_id)
        assert run is not None
        return run.plan_id


def failed_do_it_run(workflow_id: UUID, plan_id: UUID) -> RunRow:
    return RunRow(
        plan_id=plan_id, plan_revision=1, status="failed", kind="do_it", source_workflow_id=workflow_id,
        finished_at=datetime.now(UTC),
    )  # fmt: skip
