"""Queries the run engine and the API need. Every function works inside the caller's transaction and never
commits, so a run transition and its event are written together or not at all:

    async with sessions.begin() as session:
        event = await transition_run(session, run_id, to="running", allowed_from=("queued",), ...)
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import ColumnElement, and_, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts_gen.events_schema import RunEvent
from app.db.models import PlanRow, RunEventRow, RunRow, TaskRow, WorkflowRow

_EVENTS: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)
# Columns a transition may change besides status; anything else is a programming error.
_RUN_FIELDS = frozenset(
    {"current_seq", "retry_count", "error", "started_at", "finished_at", "duration_ms", "browser_session"}
)
_EVENT_COLUMNS = frozenset({"type", "run_id", "seq", "ts"})


class InvalidRunEventError(ValueError):
    """The event doesn't match the contract (events.schema.json), so it is never stored."""


# --- runs and run_events ---------------------------------------------------------------------------------


async def transition_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    to: str,
    allowed_from: Iterable[str],
    event_type: str,
    event_data: Mapping[str, Any],
    **changes: Any,
) -> RunEventRow | None:
    """Move a run to `to` if its status is in `allowed_from`, and record the event in the same transaction.

    Returns the stored event, or None if the run doesn't exist or isn't in an allowed status (an illegal
    transition, or another task got there first). The conditional UPDATE takes a row lock, so of two racing
    transitions exactly one wins.
    """
    unknown = changes.keys() - _RUN_FIELDS
    if unknown:
        raise ValueError(f"transition_run can't change {sorted(unknown)}")
    seq = await _bump_seq(session, run_id, RunRow.status.in_(list(allowed_from)), status=to, **changes)
    if seq is None:
        return None
    return await _insert_event(session, run_id, seq, event_type, event_data)


async def append_event(
    session: AsyncSession,
    run_id: UUID,
    event_type: str,
    event_data: Mapping[str, Any],
    *,
    while_status: Iterable[str] | None = None,
    **changes: Any,
) -> RunEventRow | None:
    """Record an event that doesn't change the status (e.g. `step.verified`), optionally only while the run
    is in `while_status` (so a step event can't land after the run was cancelled). None if that didn't hold.
    """
    unknown = changes.keys() - _RUN_FIELDS
    if unknown:
        raise ValueError(f"append_event can't change {sorted(unknown)}")
    condition = RunRow.status.in_(list(while_status)) if while_status is not None else None
    seq = await _bump_seq(session, run_id, condition, **changes)
    if seq is None:
        return None
    return await _insert_event(session, run_id, seq, event_type, event_data)


async def events_after(
    session: AsyncSession, run_id: UUID, after_seq: int = 0, *, limit: int | None = None
) -> Sequence[RunEventRow]:
    """Events with seq > after_seq, oldest first (SSE resume with Last-Event-ID)."""
    query = (
        select(RunEventRow)
        .where(RunEventRow.run_id == run_id, RunEventRow.seq > after_seq)
        .order_by(RunEventRow.seq)
        .limit(limit)
    )
    return (await session.scalars(query)).all()


def event_payload(row: RunEventRow) -> dict[str, Any]:
    """The full contract event (`RunEvent`) as JSON-ready data, rebuilt from a stored row."""
    return {"type": row.type, "run_id": str(row.run_id), "seq": row.seq, "ts": _iso(row.ts), **row.data}


async def list_runs(
    session: AsyncSession, *, user_id: UUID, limit: int, before: tuple[datetime, UUID] | None = None
) -> Sequence[RunRow]:
    """`user_id`'s runs (through their tasks), newest first. `before` is the (created_at, id) of the last run
    on the previous page."""
    query = (
        select(RunRow)
        .join(PlanRow, PlanRow.id == RunRow.plan_id)
        .join(TaskRow, TaskRow.id == PlanRow.task_id)
        .where(TaskRow.user_id == user_id)
        .order_by(RunRow.created_at.desc(), RunRow.id.desc())
        .limit(limit)
    )
    if before is not None:
        query = query.where(tuple_(RunRow.created_at, RunRow.id) < tuple_(*before))
    return (await session.scalars(query)).all()


async def runs_with_status(session: AsyncSession, statuses: Iterable[str]) -> Sequence[UUID]:
    """Ids of runs in these statuses, e.g. the startup sweep of runs a restart interrupted."""
    query = select(RunRow.id).where(RunRow.status.in_(list(statuses))).order_by(RunRow.created_at)
    return (await session.scalars(query)).all()


async def _bump_seq(
    session: AsyncSession, run_id: UUID, condition: ColumnElement[bool] | None, **values: Any
) -> int | None:
    where = and_(RunRow.id == run_id, condition) if condition is not None else RunRow.id == run_id
    result = await session.execute(
        update(RunRow)
        .where(where)
        .values(last_event_seq=RunRow.last_event_seq + 1, updated_at=func.now(), **values)
        .returning(RunRow.last_event_seq)
    )
    return result.scalar_one_or_none()


async def _insert_event(
    session: AsyncSession, run_id: UUID, seq: int, event_type: str, data: Mapping[str, Any]
) -> RunEventRow:
    if _EVENT_COLUMNS & data.keys():
        raise InvalidRunEventError(f"event_data must not set {sorted(_EVENT_COLUMNS & data.keys())}")
    ts = datetime.now(UTC)
    payload = {"type": event_type, "run_id": str(run_id), "seq": seq, "ts": _iso(ts), **data}
    try:
        event = _EVENTS.validate_python(payload)
    except ValueError as e:  # pydantic.ValidationError is a ValueError
        raise InvalidRunEventError(f"{event_type} doesn't match the contract: {e}") from e
    stored = event.model_dump(mode="json", exclude=set(_EVENT_COLUMNS), exclude_none=True)
    row = RunEventRow(run_id=run_id, seq=seq, type=event_type, data=stored, ts=ts)
    session.add(row)
    await session.flush()
    return row


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat().replace("+00:00", "Z")


# --- plans ------------------------------------------------------------------------------------------------


async def update_plan_steps(
    session: AsyncSession, plan_id: UUID, *, revision: int, steps: list[Any], risk: str
) -> PlanRow | None:
    """Replace the steps of a proposed plan and bump its revision, only if `revision` is still current.

    None means the plan doesn't exist, was already approved/rejected, or someone saved a newer revision
    (the API answers 409).
    """
    result = await session.execute(
        update(PlanRow)
        .where(PlanRow.id == plan_id, PlanRow.revision == revision, PlanRow.status == "proposed")
        .values(steps=steps, risk=risk, revision=PlanRow.revision + 1, updated_at=func.now())
        .returning(PlanRow)
    )
    return result.scalar_one_or_none()


async def decide_plan(session: AsyncSession, plan_id: UUID, *, revision: int, to: str) -> PlanRow | None:
    """Approve or reject exactly the revision the user saw. None if it isn't proposed at that revision."""
    if to not in ("approved", "rejected"):
        raise ValueError(f"a plan can only be approved or rejected, not {to!r}")
    values: dict[str, Any] = {"status": to, "updated_at": func.now()}
    if to == "approved":
        values["approved_at"] = func.now()
    result = await session.execute(
        update(PlanRow)
        .where(PlanRow.id == plan_id, PlanRow.revision == revision, PlanRow.status == "proposed")
        .values(**values)
        .returning(PlanRow)
    )
    return result.scalar_one_or_none()


# --- workflows --------------------------------------------------------------------------------------------


async def list_workflows(
    session: AsyncSession,
    *,
    user_id: UUID,
    limit: int,
    target_app: str | None = None,
    before: tuple[datetime, UUID] | None = None,
) -> Sequence[WorkflowRow]:
    """Newest first, optionally for one app. Steps are loaded too (`selectin`), for the step count."""
    query = (
        select(WorkflowRow)
        .where(WorkflowRow.user_id == user_id)
        .order_by(WorkflowRow.created_at.desc(), WorkflowRow.id.desc())
        .limit(limit)
    )
    if target_app is not None:
        query = query.where(WorkflowRow.target_app == target_app)
    if before is not None:
        query = query.where(tuple_(WorkflowRow.created_at, WorkflowRow.id) < tuple_(*before))
    return (await session.scalars(query)).all()
