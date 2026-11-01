"""POST /workflows/{id}/regenerate (#113): re-plan a workflow that can't heal from its original task; the
approved run's steps become the workflow's next version (D3), not a new workflow."""

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.run_schema import Run
from app.contracts_gen.task_schema import Task
from app.contracts_gen.workflow_schema import Workflow, WorkflowVersionList
from app.db import WorkflowRow
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.api.test_reverify import verified_workflow
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio


async def workflow_count(sessions: Sessions) -> int:
    async with sessions() as s:
        return int(await s.scalar(select(func.count()).select_from(WorkflowRow)) or 0)


async def regenerate(api: Api, workflow_id: UUID) -> Task:
    started = await api.client.post(f"/workflows/{workflow_id}/regenerate")
    assert started.status_code == 202, started.text
    task = Task.model_validate(started.json())
    assert task.status == "planning" and task.regenerates_workflow_id == workflow_id
    await api.svc.planning.wait(task.id)
    return Task.model_validate((await api.client.get(f"/tasks/{task.id}")).json())


async def approve_and_run(api: Api, task: Task) -> tuple[Run, list[dict[str, Any]]]:
    plan = Plan.model_validate((await api.client.get(f"/plans/{task.plan_id}")).json())
    approved = await api.client.post(f"/plans/{plan.id}/approve", json={"revision": plan.revision})
    assert approved.status_code == 201, approved.text
    run = Run.model_validate(approved.json())
    stream = await api.events(run.id)
    return Run.model_validate((await api.client.get(f"/runs/{run.id}")).json()), stream


async def test_a_regenerated_run_becomes_the_workflows_next_version(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        original = Workflow.model_validate((await api.client.get(f"/workflows/{workflow_id}")).json())
        before = await workflow_count(sessions)

        task = await regenerate(api, workflow_id)
        assert task.status == "planned" and task.prompt == original.task  # the original request, re-planned
        run, stream = await approve_and_run(api, task)

        assert run.status == "verified" and run.kind == "task"
        assert stream[-1]["type"] == "run.completed" and stream[-1]["workflow_id"] == str(workflow_id)
        assert await workflow_count(sessions) == before  # no new workflow
        listed = WorkflowVersionList.model_validate(
            (await api.client.get(f"/workflows/{workflow_id}/versions")).json()
        )
        [v2, v1] = listed.items
        assert (v2.revision, v2.source, v2.status, v2.run_id) == (2, "regenerate", "current", run.id)
        assert v1.status == "superseded" and v2.parent_version_id == v1.id
        assert v2.change_summary is not None and v2.change_summary.to_revision == 2
        workflow = Workflow.model_validate((await api.client.get(f"/workflows/{workflow_id}")).json())
        assert (workflow.revision, workflow.status) == (2, "verified")
        assert workflow.recording_path is not None and str(run.id) in workflow.recording_path


async def test_only_the_owner_can_regenerate(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
    async with Api(services(sessions, tmp_path), user=await make_user(sessions)) as stranger:
        response = await stranger.client.post(f"/workflows/{workflow_id}/regenerate")
        unknown = await stranger.client.post("/workflows/6f1c2a4e-1111-4b8a-9a1b-123456789abc/regenerate")

    assert response.status_code == 404 and unknown.status_code == 404
