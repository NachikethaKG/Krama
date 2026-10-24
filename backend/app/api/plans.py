"""GET/PATCH /plans/{id}, POST /plans/{id}/approve and /reject (docs/api-contract.md)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.auth import CurrentUser
from app.api.convert import plan_out, run_out
from app.api.errors import ApiException
from app.api.owner import owned_plan
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.plan_schema import Plan, PlanApproveRequest, PlanRejectRequest, PlanUpdateRequest
from app.contracts_gen.run_schema import Run
from app.db import PlanRow, RunRow
from app.db.repositories import decide_plan, update_plan_steps
from app.planner.planner import LLMPlan, check_steps

type Responses = dict[int | str, dict[str, Any]]

router = APIRouter(tags=["plans"])
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
_404: Responses = {404: {"model": ErrorResponse, "description": "No plan with this id"}}
_409: Responses = {
    409: {"model": ErrorResponse, "description": "Plan already approved/rejected, or a stale revision"}
}


@router.get("/plans/{plan_id}", responses=_404)
async def get_plan(plan_id: UUID, user: CurrentUser, services: ServicesDep) -> Plan:
    async with services.sessions() as s:
        return plan_out(await owned_plan(s, plan_id, user))


@router.patch("/plans/{plan_id}", responses={**_404, **_409})
async def update_plan(
    plan_id: UUID, body: PlanUpdateRequest, user: CurrentUser, services: ServicesDep
) -> Plan:
    """Replaces the steps (reorder / delete / edit) and bumps the revision. The same rules as for a fresh
    plan apply, and the plan's risk is recomputed from its steps."""
    steps = [step.model_copy(update={"seq": i}) for i, step in enumerate(body.steps, start=1)]
    async with services.sessions.begin() as s:
        current = await owned_plan(s, plan_id, user)
        problems = check_steps(LLMPlan(expected_result=current.expected_result, steps=steps))
        if problems:
            raise ApiException(422, "validation_error", "Invalid plan steps", {"problems": problems})
        risk = max((step.risk for step in steps), key=_RISK_ORDER.__getitem__)
        updated = await update_plan_steps(
            s,
            plan_id,
            revision=body.revision,
            steps=[step.model_dump(mode="json", exclude_none=True) for step in steps],
            risk=risk,
        )
        if updated is None:
            _raise_not_editable(current, body.revision)
        assert updated is not None
        await s.refresh(updated)  # the UPDATE ran behind the identity map's back
        return plan_out(updated)


@router.post("/plans/{plan_id}/approve", status_code=201, responses={**_404, **_409})
async def approve_plan(
    plan_id: UUID, body: PlanApproveRequest, user: CurrentUser, services: ServicesDep
) -> Run:
    """Approves exactly the revision the user saw and queues a run of it."""
    async with services.sessions.begin() as s:
        current = await owned_plan(s, plan_id, user)
        approved = await decide_plan(s, plan_id, revision=body.revision, to="approved")
        if approved is None:
            _raise_not_editable(current, body.revision)
        run = RunRow(plan_id=plan_id, plan_revision=body.revision, status="queued")
        s.add(run)
        await s.flush()
        out = run_out(run, None)
    await services.executor.submit(run.id)
    return out


@router.post("/plans/{plan_id}/reject", responses={**_404, **_409})
async def reject_plan(
    plan_id: UUID, body: PlanRejectRequest, user: CurrentUser, services: ServicesDep
) -> Plan:
    async with services.sessions.begin() as s:
        current = await owned_plan(s, plan_id, user)
        rejected = await decide_plan(s, plan_id, revision=current.revision, to="rejected")
        if rejected is None:
            _raise_not_editable(current, current.revision)
        assert rejected is not None
        await s.refresh(rejected)
        return plan_out(rejected)


def _raise_not_editable(current: PlanRow, revision: int) -> None:
    details: dict[str, Any] = {"status": current.status, "revision": current.revision}
    if current.status != "proposed":
        raise ApiException(409, "plan_not_editable", f"Plan is already {current.status}", details)
    raise ApiException(
        409, "conflict", f"Plan revision {revision} is stale; the current one is {current.revision}", details
    )
