"""POST /tasks, GET /tasks/{id}, POST /tasks/{id}/clarify (docs/api-contract.md)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.convert import task_out
from app.api.errors import ApiException
from app.api.owner import owned_task
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.task_schema import Task, TaskClarifyRequest, TaskCreateRequest
from app.db import PlanRow, TaskRow

type Responses = dict[int | str, dict[str, Any]]

router = APIRouter(tags=["tasks"])
_404: Responses = {404: {"model": ErrorResponse, "description": "No task with this id"}}


@router.post("/tasks", status_code=202)
async def create_task(body: TaskCreateRequest, user: CurrentUser, services: ServicesDep) -> Task:
    """Starts planning in the background. Poll GET /tasks/{id} until it is planned, needs clarification or
    failed."""
    async with services.sessions.begin() as s:
        task = TaskRow(
            user_id=user.id,
            prompt=body.prompt,
            target_url=str(body.target_url).rstrip("/"),
            status="planning",
        )
        s.add(task)
        await s.flush()
        out = task_out(task, None)
    services.planning.submit(task.id)
    return out


@router.get("/tasks/{task_id}", responses=_404)
async def get_task(task_id: UUID, user: CurrentUser, services: ServicesDep) -> Task:
    async with services.sessions() as s:
        task = await owned_task(s, task_id, user)
        return task_out(task, await _latest_plan_id(s, task_id))


@router.post(
    "/tasks/{task_id}/clarify",
    status_code=202,
    responses={**_404, 409: {"model": ErrorResponse, "description": "The task isn't waiting for an answer"}},
)
async def clarify_task(
    task_id: UUID, body: TaskClarifyRequest, user: CurrentUser, services: ServicesDep
) -> Task:
    """Answers the planner's question and plans again."""
    async with services.sessions.begin() as s:
        task = await owned_task(s, task_id, user, for_update=True)
        if task.status != "needs_clarification":
            raise ApiException(409, "conflict", "The task is not waiting for a clarification")
        # The answer travels with the prompt, so the planner sees both (no extra column for Phase 1).
        task.prompt = f"{task.prompt}\n\nQ: {task.clarification_question}\nA: {body.answer}"
        task.status, task.clarification_question = "planning", None
        await s.flush()
        out = task_out(task, await _latest_plan_id(s, task_id))
    services.planning.submit(task_id)
    return out


async def _latest_plan_id(s: AsyncSession, task_id: UUID) -> UUID | None:
    query = select(PlanRow.id).where(PlanRow.task_id == task_id).order_by(PlanRow.created_at.desc()).limit(1)
    plan_id: UUID | None = await s.scalar(query)
    return plan_id
