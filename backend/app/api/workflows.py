"""GET /workflows/{id} (the Verified Workflow, the main output), its text guide, and GET /workflows
(docs/api-contract.md)."""

from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.api.convert import decode_cursor, encode_cursor, run_out, workflow_out, workflow_summary
from app.api.errors import ApiException
from app.api.guide import guide_markdown
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.run_schema import Run
from app.contracts_gen.workflow_schema import Workflow, WorkflowPage
from app.db import PlanRow, RunRow, TaskRow, WorkflowRow
from app.db.repositories import list_workflows
from app.runs.reverify import ReverifyRefusedError, check_replayable, plan_risk, plan_steps
from app.targets import ResetError

router = APIRouter(tags=["workflows"])


@router.get("/workflows/{workflow_id}", responses={404: {"model": ErrorResponse, "description": "Not found"}})
async def get_workflow(workflow_id: UUID, services: ServicesDep) -> Workflow:
    async with services.sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        if workflow is None:
            raise ApiException(404, "not_found", "Workflow not found")
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
async def get_workflow_guide(workflow_id: UUID, request: Request, services: ServicesDep) -> Response:
    """The workflow as a plain text guide: the tutorial's step texts, numbered, each with its screenshot."""
    workflow = await get_workflow(workflow_id, services)

    def artifact_url(key: str) -> str:
        # Absolute, so the file still shows its images when opened outside the app.
        return str(request.url_for("get_artifact", key=quote(key)))

    return Response(
        guide_markdown(workflow, artifact_url),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'inline; filename="workflow-{workflow_id}.md"'},
    )


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
async def reverify_workflow(workflow_id: UUID, services: ServicesDep) -> Run:
    """Replay the stored workflow's steps headlessly, without the planner (#77). The run stores no new
    workflow; its events and final status say whether every step still works."""
    async with services.sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        if workflow is None:
            raise ApiException(404, "not_found", "Workflow not found")
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
    services: ServicesDep,
    target_app: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> WorkflowPage:
    """Stored workflows, newest first, optionally for one app (e.g. gitea)."""
    async with services.sessions() as s:
        rows = await list_workflows(s, limit=limit, target_app=target_app, before=decode_cursor(cursor))
        items = [workflow_summary(r) for r in rows]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return WorkflowPage(items=items, next_cursor=next_cursor)
