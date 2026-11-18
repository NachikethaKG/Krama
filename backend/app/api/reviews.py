"""The owner's review queue (#115/#377, docs/api-contract.md): list, count, accept / reject a waiting fix, and
retry the AI fix of an outdated workflow. The queue is derived in `app.runs.reviews`."""

from typing import Annotated, Any, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends

from app.agent.quota import RedisHealBudget
from app.api.auth import CurrentUser
from app.api.convert import run_out
from app.api.errors import ApiException
from app.api.owner import owned_workflow
from app.api.services import ServicesDep
from app.config import get_settings
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.review_schema import ReviewActionResult, ReviewCount, ReviewItemList
from app.contracts_gen.run_schema import Run
from app.db import RunRow
from app.runs.reverify import ReverifyRefusedError, create_reverify_run
from app.runs.reviews import ReviewConflictError, ReviewNotFoundError, accept, reject, review_items, utcnow

router = APIRouter(tags=["reviews"])

_404: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse, "description": "Not found"}}


class AiFixBudget(Protocol):
    async def remaining(self) -> int: ...


def get_ai_fix_budget() -> AiFixBudget:
    """Today's Gemini heal budget (D12), shared with the worker through Redis."""
    return RedisHealBudget(get_settings().redis_url)


BudgetDep = Annotated[AiFixBudget, Depends(get_ai_fix_budget)]


@router.get("/reviews")
async def get_reviews(user: CurrentUser, services: ServicesDep, budget: BudgetDep) -> ReviewItemList:
    left = await budget.remaining() > 0
    async with services.sessions() as s:
        return ReviewItemList(items=await review_items(s, user.id, ai_fix_left=left, now=utcnow()))


@router.get("/reviews/count")
async def get_review_count(user: CurrentUser, services: ServicesDep) -> ReviewCount:
    async with services.sessions() as s:
        items = await review_items(s, user.id, ai_fix_left=False, now=utcnow())
    return ReviewCount(count=len(items))


_ACTION_RESPONSES: dict[int | str, dict[str, Any]] = {
    **_404,
    409: {"model": ErrorResponse, "description": "The fix no longer waits for review, or isn't a fix"},
}


@router.post("/reviews/{item_id}/accept", responses=_ACTION_RESPONSES)
async def accept_review(item_id: str, user: CurrentUser, services: ServicesDep) -> ReviewActionResult:
    """D8: the waiting version becomes the live one."""
    return await _act(accept, item_id, user.id, services)


@router.post("/reviews/{item_id}/reject", responses=_ACTION_RESPONSES)
async def reject_review(item_id: str, user: CurrentUser, services: ServicesDep) -> ReviewActionResult:
    """D8: the waiting version is thrown away; the workflow stays outdated."""
    return await _act(reject, item_id, user.id, services)


async def _act(action: Any, item_id: str, user_id: UUID, services: ServicesDep) -> ReviewActionResult:
    try:
        async with services.sessions.begin() as s:
            result: ReviewActionResult = await action(s, user_id, item_id)
            return result
    except ReviewNotFoundError:
        raise ApiException(404, "not_found", "Review item not found") from None
    except ReviewConflictError as e:
        raise ApiException(409, "conflict", str(e), {"reason": "not_pending"}) from None


@router.post(
    "/workflows/{workflow_id}/retry-ai-fix",
    status_code=202,
    responses={
        **_404,
        409: {"model": ErrorResponse, "description": "The workflow can't be replayed"},
        429: {"model": ErrorResponse, "description": "Today's AI fix budget is used up"},
    },
)
async def retry_ai_fix(workflow_id: UUID, user: CurrentUser, services: ServicesDep, budget: BudgetDep) -> Run:
    """Replay the workflow with the Gemini heal allowed (D12): a reverify run whose heal may ask Gemini to
    choose among the candidates. A new version it saves shows up in the queue as `heal_pending`."""
    async with services.sessions() as s:
        workflow = await owned_workflow(s, workflow_id, user)
        target_url = workflow.target_url
    if await budget.remaining() <= 0:
        raise ApiException(
            429,
            "rate_limited",
            "Today's AI fix quota (5/day) is used up. Regenerate the tutorial, or retry tomorrow.",
            {"reason": "ai_fix_quota"},
        )
    try:
        run_id = await create_reverify_run(services.sessions, workflow_id, services.target(target_url).reset)
    except ReverifyRefusedError as e:
        raise ApiException(409, "conflict", str(e), {"reason": e.reason}) from None
    async with services.sessions() as s:
        run = await s.get(RunRow, run_id)
        assert run is not None
        out = run_out(run, None)
    await services.executor.submit(run_id)
    return out
