"""GET /workflows/{id} (the Verified Workflow, the main output), its text guide and versions, and
GET /workflows (docs/api-contract.md)."""

from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.api.auth import CurrentUser
from app.api.convert import (
    decode_cursor,
    encode_cursor,
    run_out,
    task_out,
    version_out,
    workflow_out,
    workflow_summary,
)
from app.api.errors import ApiException
from app.api.guide import guide_markdown
from app.api.owner import owned_workflow
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.run_schema import Run
from app.contracts_gen.task_schema import Task
from app.contracts_gen.workflow_schema import Workflow, WorkflowPage, WorkflowVersionList
from app.db import PlanRow, RunRow, TaskRow
from app.db.repositories import list_versions, list_workflows
from app.runs.reverify import ReverifyRefusedError, check_replayable, plan_risk, plan_steps
from app.targets import ResetError

router = APIRouter(tags=["workflows"])


@router.get("/workflows/{workflow_id}", responses={404: {"model": ErrorResponse, "description": "Not found"}})
async def get_workflow(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> Workflow:
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        task = await s.get(TaskRow, workflow.task_id)
        return workflow_out(workflow, task.prompt if task else None)


@router.get(
    "/workflows/{workflow_id}/guide.md",
    response_class=Response,
    responses={
        200: {"content": {"text/markdown": {}}, "description": "Numbered steps with one screenshot each"},
        404: {"model": ErrorResponse, "description": "Not found"},
    },
)
async def get_workflow_guide(
    workflow_id: UUID, request: Request, user: CurrentUser, services: ServicesDep
) -> Response:
    """The workflow as a plain text guide: the tutorial's step texts, numbered, each with its screenshot."""
    workflow = await get_workflow(workflow_id, user, services)

    def artifact_url(key: str) -> str:
        # Absolute, so the file still shows its images when opened outside the app.
        return str(request.url_for("get_artifact", key=quote(key)))

    return Response(
        guide_markdown(workflow, artifact_url),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="workflow-{workflow_id}.md"'},
    )


@router.get(
    "/workflows/{workflow_id}/versions", responses={404: {"model": ErrorResponse, "description": "Not found"}}
)
async def get_workflow_versions(
    workflow_id: UUID, user: CurrentUser, services: ServicesDep
) -> WorkflowVersionList:
    """Every version of the workflow, newest first, each with its step diff against its parent (Phase 4)."""
    async with services.sessions() as s:
        await owned_workflow(s, workflow_id, user)
        return WorkflowVersionList(items=[version_out(v, n) for v, n in await list_versions(s, workflow_id)])


@router.post(
    "/workflows/{workflow_id}/regenerate",
    status_code=202,
    responses={404: {"model": ErrorResponse, "description": "Not found"}},
)
async def regenerate_workflow(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> Task:
    """Re-plan a workflow that can't heal (#113), from its original prompt and URL. Like POST /tasks: poll the
    task, then review and approve its plan. When that run verifies, its steps become this workflow's next
    version (D3); no new workflow."""
    async with services.sessions.begin() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        original = await s.get(TaskRow, workflow.task_id)
        task = TaskRow(
            user_id=user.id,
            prompt=original.prompt if original else workflow.title,
            target_url=workflow.target_url,
            status="planning",
            regenerates_workflow_id=workflow.id,
        )
        s.add(task)
        await s.flush()
        out = task_out(task, None)
    services.planning.submit(task.id)
    return out


@router.post(
    "/workflows/{workflow_id}/reverify",
    status_code=202,
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {
            "model": ErrorResponse,
            "description": "A step is high risk or typed a secret, or the reset failed",
        },
    },
)
async def reverify_workflow(workflow_id: UUID, user: CurrentUser, services: ServicesDep) -> Run:
    """Replay the stored workflow's steps headlessly, without the planner (#77). The run stores no new
    workflow; its events and final status say whether every step still works."""
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        steps = list(workflow.steps)
        task_id, target_url, title = workflow.task_id, workflow.target_url, workflow.title
    try:
        check_replayable(steps)
    except ReverifyRefusedError as e:
        raise ApiException(409, "conflict", str(e), {"reason": e.reason, "step_seq": e.step_seq}) from None
    reset = services.target(target_url).reset
    if reset is not None:
        # Undo what the workflow creates, so the replay starts where the recorded run did.
        stored = [{"seq": st.seq, "action": st.action, "target": st.target, "before_state": st.before_state}
                  for st in steps]  # fmt: skip
        try:
            await reset(stored)
        except ResetError as e:
            raise ApiException(
                409, "conflict", f"The target couldn't be reset: {e}", {"reason": "reset_failed"}
            ) from None
    async with services.sessions.begin() as s:
        plan = PlanRow(
            task_id=task_id,
            status="approved",
            risk=plan_risk(steps),
            expected_result=title,
            steps=plan_steps(steps),
            approved_at=datetime.now(UTC),
        )
        s.add(plan)
        await s.flush()
        run = RunRow(
            plan_id=plan.id, plan_revision=1, status="queued", kind="reverify", source_workflow_id=workflow_id
        )
        s.add(run)
        await s.flush()
        out = run_out(run, None)
    await services.executor.submit(run.id)
    return out


@router.get("/workflows")
async def get_workflows(
    user: CurrentUser,
    services: ServicesDep,
    target_app: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> WorkflowPage:
    """Stored workflows, newest first, optionally for one app (e.g. gitea)."""
    async with services.sessions() as s:
        rows = await list_workflows(
            s, user_id=user.id, limit=limit, target_app=target_app, before=decode_cursor(cursor)
        )
        items = [workflow_summary(r) for r in rows]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return WorkflowPage(items=items, next_cursor=next_cursor)
