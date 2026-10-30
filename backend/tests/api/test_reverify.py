"""POST /workflows/{id}/reverify (#77) end to end: a stored workflow replayed by the real executor (real
Postgres, Chromium, observer and verifier on the local test site), without the planner and without a new
workflow.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select, update

from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.run_schema import Run
from app.db import WorkflowRow, WorkflowStepRow
from app.targets import ResetError, TargetSetup
from tests.api.test_flow import Api, Sessions, reply, services
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio


async def verified_workflow(api: Api, site: str) -> UUID:
    """The normal flow: plan (fake LLM) -> approve -> run -> stored workflow."""
    task = await api.planned_task(site)
    plan = Plan.model_validate((await api.client.get(f"/plans/{task.plan_id}")).json())
    approved = await api.client.post(f"/plans/{plan.id}/approve", json={"revision": plan.revision})
    run = Run.model_validate(approved.json())
    stream = await api.events(run.id)
    assert stream[-1]["type"] == "run.completed", stream[-1]
    return UUID(stream[-1]["workflow_id"])


async def reverify(api: Api, workflow_id: UUID) -> tuple[Run, list[dict[str, Any]]]:
    started = await api.client.post(f"/workflows/{workflow_id}/reverify")
    assert started.status_code == 202, started.text
    run = Run.model_validate(started.json())
    stream = await api.events(run.id)
    return Run.model_validate((await api.client.get(f"/runs/{run.id}")).json()), stream


async def change_step(sessions: Sessions, workflow_id: UUID, seq: int, **values: Any) -> None:
    async with sessions.begin() as s:
        await s.execute(
            update(WorkflowStepRow)
            .where(WorkflowStepRow.workflow_id == workflow_id, WorkflowStepRow.seq == seq)
            .values(**values)
        )


async def workflow_count(sessions: Sessions) -> int:
    async with sessions() as s:
        return int((await s.execute(select(func.count()).select_from(WorkflowRow))).scalar_one())


async def test_a_stored_workflow_replays_without_a_new_workflow(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        before = await workflow_count(sessions)

        run, stream = await reverify(api, workflow_id)

        assert (run.kind, run.source_workflow_id, run.status, run.workflow_id) == (
            "reverify", workflow_id, "verified", None
        )  # fmt: skip
        assert [e["type"] for e in stream] == [
            "run.started",
            *["step.started", "step.action_done", "step.verified"] * 4,
            "run.completed",
        ]
        assert stream[-1]["workflow_id"] == str(workflow_id) and stream[-1]["verified_steps"] == 4
        assert await workflow_count(sessions) == before  # no duplicate
        # The run replayed exactly the stored steps, as an approved plan nobody had to approve again.
        plan = Plan.model_validate((await api.client.get(f"/plans/{run.plan_id}")).json())
        assert plan.status == "approved" and [s.seq for s in plan.steps] == [1, 2, 3, 4]


async def test_a_step_whose_element_is_gone_fails_as_a_locator_miss(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        # The UI "changed": step 1's link is now called something else.
        await change_step(sessions, workflow_id, 1, target={"role": "link", "name": "Add an item"})

        run, stream = await reverify(api, workflow_id)

        assert run.status == "failed" and run.error is not None
        details = run.error.details or {}
        assert (details["reason"], details["step_seq"], details["error_code"]) == (
            "locator_miss",
            1,
            "target_not_found",
        )
        assert details["target"] == {"role": "link", "name": "Add an item"}
        # The evidence for validation (#109): the links the page did offer, the real one among them.
        assert "New item" in {c["name"] for c in details["candidates"]}
        assert all(c["role"] == "link" and len(c["bbox"]) == 4 for c in details["candidates"])
        assert "failed_checks" not in details
        assert "no longer works" in run.error.message
        # No replan, no pause, and the later steps (which depend on step 1) never ran.
        types = [e["type"] for e in stream]
        assert "run.replanning" not in types and "run.paused" not in types
        assert {e.get("step_seq") for e in stream if e["type"] == "step.started"} == {1}


async def test_a_step_that_runs_but_no_longer_reaches_its_state_is_a_state_mismatch(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 4, expected_state={"url_matches": "^/somewhere-else$"})

        run, _ = await reverify(api, workflow_id)

        assert run.status == "failed" and run.error is not None
        details = run.error.details or {}
        assert (details["reason"], details["step_seq"]) == ("state_mismatch", 4)
        assert "candidates" not in details and "error_code" not in details
        [check] = details["failed_checks"]
        assert (check["kind"], check["expected"]) == ("url_matches", "^/somewhere-else$")
        assert check["detail"]  # what the page showed instead, e.g. "path is '/done'"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"risk": "high"}, "high_risk_step"),
        ({"sensitive": True, "action": {"type": "fill", "value": "***"}}, "secret_not_stored"),
    ],
)
async def test_steps_a_headless_replay_must_not_run_are_refused(
    sessions: Sessions, tmp_path: Path, site: str, change: dict[str, Any], reason: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 2, **change)

        refused = await api.client.post(f"/workflows/{workflow_id}/reverify")

        assert refused.status_code == 409
        error = refused.json()["error"]
        assert error["code"] == "conflict" and error["details"] == {"reason": reason, "step_seq": 2}


async def test_the_target_is_reset_first_and_a_failed_reset_refuses(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    svc = services(sessions, tmp_path, reply(GOOD_PLAN))
    seen: list[list[int]] = []

    async def reset(steps: Sequence[Any]) -> list[str]:
        seen.append([s["seq"] for s in steps])
        return ["undone"]

    async def broken(steps: Sequence[Any]) -> list[str]:
        raise ResetError("Gitea isn't reachable")

    async with Api(svc) as api:
        workflow_id = await verified_workflow(api, site)

        svc.target = lambda _url: TargetSetup(reset=reset)
        run, _ = await reverify(api, workflow_id)
        assert seen == [[1, 2, 3, 4]] and run.status == "verified"

        svc.target = lambda _url: TargetSetup(reset=broken)
        refused = await api.client.post(f"/workflows/{workflow_id}/reverify")
        assert refused.status_code == 409 and refused.json()["error"]["details"] == {"reason": "reset_failed"}


async def test_an_unknown_workflow_is_404(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        response = await api.client.post("/workflows/6f1c2a4e-1111-4b8a-9a1b-123456789abc/reverify")

        assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
