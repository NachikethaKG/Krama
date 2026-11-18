"""The review queue API (#377): each category derived from stored data, accept / reject of a waiting fix (D8),
ownership, and retry-ai-fix against the daily AI budget (D12)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from app.api.reviews import get_ai_fix_budget
from app.contracts_gen.review_schema import ReviewItemList
from app.db import ValidationRow, WorkflowRow, WorkflowStepRow, WorkflowVersionRow
from app.db.repositories import add_workflow_version
from app.runs import InProcessExecutor
from tests.api.test_exports import stored_workflow
from tests.api.test_flow import Api, Sessions, make_user, services

pytestmark = pytest.mark.anyio

DIFF = {
    "from_revision": 1,
    "to_revision": 2,
    "steps": [
        {"kind": "same", "old_seq": 1, "new_seq": 1, "category": None, "fields": []},
        {
            "kind": "changed",
            "old_seq": 2,
            "new_seq": 2,
            "category": "behaviour",
            "fields": [{"field": "target.name", "from": "Create Repository", "to": "Make Repository"}],
        },
    ],
}


class Budget:
    def __init__(self, left: int) -> None:
        self.left = left

    async def remaining(self) -> int:
        return self.left


class ReviewApi(Api):
    def __init__(self, sessions: Sessions, tmp_path: Path, budget: int = 3, **kw: Any) -> None:
        super().__init__(services(sessions, tmp_path), **kw)
        self.app.dependency_overrides[get_ai_fix_budget] = lambda: Budget(budget)

    async def __aenter__(self) -> "ReviewApi":
        await super().__aenter__()
        return self

    async def queue(self) -> ReviewItemList:
        r = await self.client.get("/reviews")
        assert r.status_code == 200, r.text
        return ReviewItemList.model_validate(r.json())


async def validation(
    sessions: Sessions, workflow_id: UUID, status: str, ago: timedelta, **details: Any
) -> None:
    async with sessions.begin() as s:
        s.add(
            ValidationRow(
                workflow_id=workflow_id, status=status, drift_details=details, ran_at=datetime.now(UTC) - ago
            )
        )


async def set_status(sessions: Sessions, workflow_id: UUID, status: str) -> None:
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None
        workflow.status = status


async def pending_heal(sessions: Sessions, workflow_id: UUID) -> UUID:
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None
        steps = (
            await s.scalars(select(WorkflowStepRow).where(WorkflowStepRow.workflow_id == workflow_id))
        ).all()
        fields = (
            "seq",
            "action",
            "target",
            "instruction_text",
            "expected_state",
            "observed_state",
            "verification",
        )
        copy = [WorkflowStepRow(**{c: getattr(st, c) for c in fields}, risk=st.risk) for st in steps]
        version = await add_workflow_version(
            s,
            workflow,
            copy,
            source="heal",
            status="pending_review",
            run_id=None,
            confidence=0.8,
            recording_path="runs/healed/rrweb_recording.json",
            viewport=None,
            change_summary=DIFF,
        )
        return version.id


async def test_a_new_owner_has_an_empty_queue(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        await stored_workflow(sessions, api.user)
        queue = await api.queue()
        count = (await api.client.get("/reviews/count")).json()
    assert queue.items == [] and count == {"count": 0}


async def test_an_outdated_workflow_says_which_step_broke(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        await set_status(sessions, workflow_id, "outdated")
        await validation(
            sessions, workflow_id, "outdated", timedelta(hours=1), reason="locator_miss", step_seq=2
        )
        [item] = (await api.queue()).items
        count = (await api.client.get("/reviews/count")).json()["count"]

    assert (item.id, item.category, item.step_seq) == (f"outdated:{workflow_id}", "outdated", 2)
    assert item.reason == "Step 2: the element it uses is gone or renamed."
    assert item.actions == ["regenerate", "retry_ai_fix"] and count == 1


async def test_no_retry_ai_fix_offered_when_the_budget_is_used_up(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path, budget=0) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        await set_status(sessions, workflow_id, "outdated")
        [item] = (await api.queue()).items
        retry = await api.client.post(f"/workflows/{workflow_id}/retry-ai-fix")
    assert item.actions == ["regenerate"]
    assert retry.status_code == 429 and retry.json()["error"]["code"] == "rate_limited"


async def test_accepting_a_waiting_fix_makes_it_live(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        version_id = await pending_heal(sessions, workflow_id)
        [item] = (await api.queue()).items
        accepted = await api.client.post(f"/reviews/{item.id}/accept")
        after = await api.queue()
        again = await api.client.post(f"/reviews/{item.id}/accept")

    assert (item.category, item.pending_revision, item.current_revision, item.step_seq) == (
        "heal_pending",
        2,
        1,
        2,
    )
    assert item.step_diff is not None and item.actions == ["accept", "reject", "regenerate"]
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["workflow_status"] == "verified" and accepted.json()["revision"] == 2
    assert after.items == []
    assert again.status_code == 409
    async with sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        statuses = dict(
            (
                await s.execute(
                    select(WorkflowVersionRow.revision, WorkflowVersionRow.status).where(
                        WorkflowVersionRow.workflow_id == workflow_id
                    )
                )
            ).all()
        )
    assert workflow is not None and workflow.current_version_id == version_id
    assert workflow.recording_path == "runs/healed/rrweb_recording.json"
    assert statuses == {1: "superseded", 2: "current"}


async def test_rejecting_a_fix_leaves_the_workflow_outdated(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        await pending_heal(sessions, workflow_id)
        [item] = (await api.queue()).items
        rejected = await api.client.post(f"/reviews/{item.id}/reject")
        [after] = (await api.queue()).items

    assert rejected.status_code == 200 and rejected.json()["workflow_status"] == "outdated"
    assert after.category == "outdated" and after.workflow_id == workflow_id


async def test_items_of_other_owners_and_bad_ids_are_404(sessions: Sessions, tmp_path: Path) -> None:
    owner = await make_user(sessions)
    workflow_id = await stored_workflow(sessions, owner)
    version_id = await pending_heal(sessions, workflow_id)
    async with ReviewApi(sessions, tmp_path) as stranger:
        theirs = await stranger.client.post(f"/reviews/heal_pending:{version_id}/accept")
        garbage = await stranger.client.post("/reviews/heal_pending:not-a-uuid/reject")
        queue = await stranger.queue()
        retry = await stranger.client.post(f"/workflows/{workflow_id}/retry-ai-fix")
    assert (theirs.status_code, garbage.status_code, retry.status_code) == (404, 404, 404)
    assert queue.items == []


async def test_only_a_waiting_fix_can_be_accepted(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        response = await api.client.post(f"/reviews/outdated:{workflow_id}/accept")
    assert response.status_code == 409


async def test_three_blocked_checks_in_a_row_cant_be_checked(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        two = await stored_workflow(sessions, api.user)
        three = await stored_workflow(sessions, api.user)
        for hours in (1, 2):
            await validation(sessions, two, "blocked", timedelta(hours=hours), reason="auth_wall")
        for hours in (1, 2, 3):
            await validation(sessions, three, "blocked", timedelta(hours=hours), reason="auth_wall")
        [item] = (await api.queue()).items

    assert (item.workflow_id, item.category) == (three, "cant_check")
    assert item.reason == "The last 3 checks were blocked: the site asked to sign in."
    assert item.actions == ["retry_check"]


async def test_two_flakes_in_a_week_is_unstable(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        recent = await stored_workflow(sessions, api.user)
        stale = await stored_workflow(sessions, api.user)
        flake = {"reason": "locator_miss", "step_seq": 3, "run_id": "x"}
        for days in (1, 3):
            await validation(sessions, recent, "passed", timedelta(days=days), flake=flake)
        for days in (1, 9):  # one is older than a week
            await validation(sessions, stale, "passed", timedelta(days=days), flake=flake)
        [item] = (await api.queue()).items

    assert (item.workflow_id, item.category, item.step_seq) == (recent, "unstable", 3)


async def test_retry_ai_fix_starts_a_reverify_run(sessions: Sessions, tmp_path: Path) -> None:
    async with ReviewApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        await set_status(sessions, workflow_id, "outdated")
        started = await api.client.post(f"/workflows/{workflow_id}/retry-ai-fix")
        executor = api.svc.executor
        assert isinstance(executor, InProcessExecutor)
        await executor.stop(UUID(started.json()["id"]))
    assert started.status_code == 202, started.text
    assert started.json()["kind"] == "reverify"
