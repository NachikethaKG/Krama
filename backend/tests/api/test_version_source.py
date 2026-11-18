"""`current_version_source` (#382): how a workflow's current version was made, in `GET /workflows/{id}` and
in the list, so the frontend can show `auto-updated` for a verified workflow that a self-heal updated."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import WorkflowRow, WorkflowStepRow
from app.db.repositories import add_workflow_version
from tests.api.test_exports import stored_workflow
from tests.api.test_flow import Api, Sessions, services

pytestmark = pytest.mark.anyio


async def heal(sessions: Sessions, workflow_id: object, status: str) -> None:
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
        await add_workflow_version(
            s, workflow, copy, source="heal", status=status, run_id=None, confidence=0.9,
            recording_path=None, viewport=None, change_summary=None,
        )  # fmt: skip


async def source_of(api: Api, workflow_id: object) -> tuple[object, object]:
    one = (await api.client.get(f"/workflows/{workflow_id}")).json()
    listed = next(
        w for w in (await api.client.get("/workflows")).json()["items"] if w["id"] == str(workflow_id)
    )
    return one["current_version_source"], listed["current_version_source"]


async def test_a_first_version_is_initial(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        assert await source_of(api, workflow_id) == ("initial", "initial")


async def test_a_published_heal_is_heal(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        await heal(sessions, workflow_id, "current")
        one = (await api.client.get(f"/workflows/{workflow_id}")).json()
        assert await source_of(api, workflow_id) == ("heal", "heal")
    assert one["status"] == "verified" and one["revision"] == 2


async def test_a_heal_waiting_for_review_isnt_the_current_version(sessions: Sessions, tmp_path: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        await heal(sessions, workflow_id, "pending_review")
        assert await source_of(api, workflow_id) == ("initial", "initial")
