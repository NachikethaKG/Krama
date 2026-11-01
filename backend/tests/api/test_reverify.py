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
from app.contracts_gen.workflow_schema import Workflow, WorkflowVersionList
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


# --- Self-healing (#112) ----------------------------------------------------------------------------------


async def rename_stored_link(
    sessions: Sessions, workflow_id: UUID, old_name: str, **fingerprint: Any
) -> None:
    """Make step 1's stored link look as if it was recorded when the page called it `old_name`: the page has
    "changed" since, and the stored locator misses."""
    async with sessions.begin() as s:
        step = await s.scalar(
            select(WorkflowStepRow).where(
                WorkflowStepRow.workflow_id == workflow_id, WorkflowStepRow.seq == 1
            )
        )
        assert step is not None and step.target["fingerprint"]["element_id"] == "new-item"
        old = {**step.target["fingerprint"], "name": old_name, **fingerprint}
        step.target = {**step.target, "name": old_name, "fingerprint": old}


class PickByName:
    """A fake Gemini heal chooser: answers with the candidate called `name`."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls = 0

    async def choose(self, page, stored, candidates, instruction, expected):  # type: ignore[no-untyped-def]
        self.calls += 1
        return next(i for i, c in enumerate(candidates) if c.name == self.name), []


class Budget:
    async def take(self) -> bool:
        return True


async def versions(api: Api, workflow_id: UUID) -> list[dict[str, Any]]:
    response = await api.client.get(f"/workflows/{workflow_id}/versions")
    assert response.status_code == 200, response.text
    return list(
        WorkflowVersionList.model_validate(response.json()).model_dump(mode="json", by_alias=True)["items"]
    )


async def test_a_renamed_link_heals_and_its_new_version_is_published(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        await rename_stored_link(sessions, workflow_id, "Add an item")

        run, stream = await reverify(api, workflow_id)

        assert run.status == "verified", run.error
        assert [e["type"] for e in stream].count("step.failed") == 1  # the miss, then the healed try verified
        [v2, v1] = await versions(api, workflow_id)
        assert (v2["revision"], v2["source"], v2["status"], v2["run_id"]) == (
            2,
            "heal",
            "current",
            str(run.id),
        )
        assert (v1["revision"], v1["status"]) == (1, "superseded") and v2["parent_version_id"] == v1["id"]
        [changed] = [s for s in v2["change_summary"]["steps"] if s["kind"] != "same"]
        assert (changed["old_seq"], changed["category"]) == (1, "behaviour")
        assert changed["fields"][0] == {"field": "target.name", "from": "Add an item", "to": "New item"}
        workflow = Workflow.model_validate((await api.client.get(f"/workflows/{workflow_id}")).json())
        assert workflow.revision == 2 and workflow.status == "verified"
        assert (
            workflow.steps[0].target.name == "New item" and "New item" in workflow.steps[0].instruction_text
        )
        assert workflow.recording_path is not None and str(run.id) in workflow.recording_path  # this run's


async def test_a_heal_gemini_chose_waits_for_review(sessions: Sessions, tmp_path: Path, site: str) -> None:
    chooser = PickByName("New item")
    async with Api(
        services(sessions, tmp_path, reply(GOOD_PLAN), heal_chooser=chooser, heal_budget=Budget())
    ) as api:
        workflow_id = await verified_workflow(api, site)
        # The stable id changed too, so scoring can't decide (0.69 < 0.75): Gemini is asked.
        await rename_stored_link(sessions, workflow_id, "Add an item", element_id="add-item")

        run, _ = await reverify(api, workflow_id)

        assert run.status == "verified" and chooser.calls == 1
        [v2, v1] = await versions(api, workflow_id)
        assert (v2["status"], v1["status"]) == ("pending_review", "current")
        workflow = Workflow.model_validate((await api.client.get(f"/workflows/{workflow_id}")).json())
        assert (workflow.status, workflow.revision) == ("outdated", 1)  # D8: a human accepts it first
        assert workflow.steps[0].target.name == "Add an item"


async def test_an_undecided_heal_fails_the_reverify_with_the_scores(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:  # no Gemini chooser
        workflow_id = await verified_workflow(api, site)
        await rename_stored_link(sessions, workflow_id, "Add an item", element_id="add-item")

        run, _ = await reverify(api, workflow_id)

        assert run.status == "failed" and run.error is not None
        details = run.error.details or {}
        assert details["reason"] == "locator_miss" and "needs 0.75 and 0.15" in details["heal"]["reason"]
        assert details["heal"]["scores"][0]["name"] == "New item"
        assert len(await versions(api, workflow_id)) == 1  # nothing saved
