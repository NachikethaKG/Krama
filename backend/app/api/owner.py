"""Who may see what (#94): everything hangs off a task, and a task belongs to the user who created it. Plans,
runs and their files follow their task; a stored workflow carries its own copy of the owner.

Someone else's resource answers exactly like a missing one (404), so ids can't be probed.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiException
from app.db import PlanRow, RunRow, TaskRow, UserRow, WorkflowRow


async def owned_task(s: AsyncSession, task_id: UUID, user: UserRow, *, for_update: bool = False) -> TaskRow:
    task = await s.get(TaskRow, task_id, with_for_update=for_update)
    if task is None or task.user_id != user.id:
        raise ApiException(404, "not_found", "Task not found")
    return task


async def owned_plan(s: AsyncSession, plan_id: UUID, user: UserRow) -> PlanRow:
    plan = await s.get(PlanRow, plan_id)
    if plan is None or await _task_owner(s, plan.task_id) != user.id:
        raise ApiException(404, "not_found", "Plan not found")
    return plan


async def owned_run(s: AsyncSession, run_id: UUID, user: UserRow) -> RunRow:
    run = await s.get(RunRow, run_id)
    if run is None or await run_owner(s, run_id) != user.id:
        raise ApiException(404, "not_found", "Run not found")
    return run


async def owned_workflow(s: AsyncSession, workflow_id: UUID, user: UserRow) -> WorkflowRow:
    workflow = await s.get(WorkflowRow, workflow_id)
    if workflow is None or workflow.user_id != user.id:
        raise ApiException(404, "not_found", "Workflow not found")
    return workflow


async def run_owner(s: AsyncSession, run_id: UUID) -> UUID | None:
    query = (
        select(TaskRow.user_id)
        .join(PlanRow, PlanRow.task_id == TaskRow.id)
        .join(RunRow, RunRow.plan_id == PlanRow.id)
        .where(RunRow.id == run_id)
    )
    owner: UUID | None = await s.scalar(query)
    return owner


async def _task_owner(s: AsyncSession, task_id: UUID) -> UUID | None:
    owner: UUID | None = await s.scalar(select(TaskRow.user_id).where(TaskRow.id == task_id))
    return owner
