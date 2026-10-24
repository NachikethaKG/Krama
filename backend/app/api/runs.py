"""GET /runs, GET /runs/{id}, POST /runs/{id}/cancel and the live view GET /runs/{id}/events (SSE).

SSE (docs/research/phase-1-vishwas-sse.md): `id:` = run_events.seq, `event:` = type, `data:` = the contract
event. On connect it sends every event after `Last-Event-ID` (0 if absent) from the database, then tails
live. It closes after a final event. FastAPI sends a `: ping` comment after 15 s of silence.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import CurrentUser
from app.api.convert import decode_cursor, encode_cursor, run_out
from app.api.errors import ApiException
from app.api.owner import owned_run
from app.api.services import ServicesDep
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.run_schema import Run, RunConfirmRequest, RunPage
from app.db import RunRow, UserRow, WorkflowRow
from app.db.repositories import event_payload, events_after, list_runs

type Responses = dict[int | str, dict[str, Any]]

router = APIRouter(tags=["runs"])
FINAL_EVENTS = frozenset({"run.completed", "run.failed", "run.cancelled"})
_404: Responses = {404: {"model": ErrorResponse, "description": "No run with this id"}}


@router.get("/runs")
async def get_runs(
    user: CurrentUser,
    services: ServicesDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> RunPage:
    """Run history, newest first."""
    before = decode_cursor(cursor)
    async with services.sessions() as s:
        rows = await list_runs(s, user_id=user.id, limit=limit, before=before)
        workflows = await _workflow_ids(s, [r.id for r in rows])
    items = [run_out(r, workflows.get(r.id)) for r in rows]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if len(rows) == limit else None
    return RunPage(items=items, next_cursor=next_cursor)


@router.get("/runs/{run_id}", responses=_404)
async def get_run(run_id: UUID, user: CurrentUser, services: ServicesDep) -> Run:
    async with services.sessions() as s:
        return await _run_out(s, run_id, user)


@router.post(
    "/runs/{run_id}/cancel",
    responses={**_404, 409: {"model": ErrorResponse, "description": "The run already finished"}},
)
async def cancel_run(run_id: UUID, user: CurrentUser, services: ServicesDep) -> Run:
    async with services.sessions() as s:
        await owned_run(s, run_id, user)  # 404 before touching someone else's run
    if not await services.executor.cancel(run_id):
        async with services.sessions() as s:
            run = await _run_out(s, run_id, user)
        raise ApiException(409, "run_not_active", f"Run already {run.status}")
    async with services.sessions() as s:
        return await _run_out(s, run_id, user)


async def existing_run(run_id: UUID, user: CurrentUser, services: ServicesDep) -> UUID:
    """Checked before the stream starts: once it has started, an error can't become a 404 any more."""
    async with services.sessions() as s:
        await owned_run(s, run_id, user)
    return run_id


@router.post(
    "/runs/{run_id}/confirm",
    responses={**_404, 409: {"model": ErrorResponse, "description": "The run isn't paused at this step"}},
)
async def confirm_run(run_id: UUID, body: RunConfirmRequest, user: CurrentUser, services: ServicesDep) -> Run:
    """Answers a paused run: `allow` runs the paused step, `deny` cancels the run."""
    async with services.sessions() as s:
        await owned_run(s, run_id, user)
    if not await services.executor.confirm(run_id, body.step_seq, body.decision):
        async with services.sessions() as s:
            run = await _run_out(s, run_id, user)
        raise ApiException(
            409, "run_not_active", f"Run is {run.status}, not paused at step {body.step_seq}",
            {"status": run.status, "current_seq": run.current_seq},
        )  # fmt: skip
    async with services.sessions() as s:
        return await _run_out(s, run_id, user)


@router.get("/runs/{run_id}/events", response_class=EventSourceResponse, responses=_404)
async def run_events(
    run_id: Annotated[UUID, Depends(existing_run)],
    services: ServicesDep,
    last_event_id: Annotated[
        int, Header(ge=0, description="Resume after this seq (sent by EventSource)")
    ] = 0,
) -> AsyncIterator[ServerSentEvent]:
    """Live view of one run. Supports `Last-Event-ID`."""
    after = last_event_id
    while True:
        seen = services.hub.version(run_id)  # before the query, so no event can slip between
        async with services.sessions() as s:  # a short session per query, never one held for the stream
            rows = await events_after(s, run_id, after)
            run = await s.get(RunRow, run_id)
        for row in rows:
            yield ServerSentEvent(data=event_payload(row), event=row.type, id=str(row.seq))
            after = row.seq
            if row.type in FINAL_EVENTS:
                return
        if run is None or (run.status in ("verified", "failed", "cancelled") and not rows):
            return  # finished, and the client already has the final event
        await services.hub.wait(run_id, seen)


async def _run_out(s: AsyncSession, run_id: UUID, user: UserRow) -> Run:
    run = await owned_run(s, run_id, user)
    return run_out(run, (await _workflow_ids(s, [run_id])).get(run_id))


async def _workflow_ids(s: AsyncSession, run_ids: list[UUID]) -> dict[UUID, UUID]:
    if not run_ids:
        return {}
    rows = await s.execute(select(WorkflowRow.run_id, WorkflowRow.id).where(WorkflowRow.run_id.in_(run_ids)))
    return {run_id: workflow_id for run_id, workflow_id in rows.all()}
