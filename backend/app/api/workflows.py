"""GET /workflows/{id} (the Verified Workflow, the main output) and GET /workflows (docs/api-contract.md)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.convert import decode_cursor, encode_cursor, workflow_out, workflow_summary
from app.api.errors import ApiException
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.workflow_schema import Workflow, WorkflowPage
from app.db import TaskRow, WorkflowRow
from app.db.repositories import list_workflows

router = APIRouter(tags=["workflows"])


@router.get("/workflows/{workflow_id}", responses={404: {"model": ErrorResponse, "description": "Not found"}})
async def get_workflow(workflow_id: UUID, services: ServicesDep) -> Workflow:
    async with services.sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        if workflow is None:
            raise ApiException(404, "not_found", "Workflow not found")
        task = await s.get(TaskRow, workflow.task_id)
        return workflow_out(workflow, task.prompt if task else None)


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
