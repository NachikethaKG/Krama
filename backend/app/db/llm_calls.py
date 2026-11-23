"""LLM usage in the database (#464): the sink for `RecordingProvider`, and the usage report."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.types import Date

from app.db.models import LLMCallRow
from app.llm.base import LLMAttempt


class DbCallSink:
    """Writes one row per attempt, in its own short transaction."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def record(self, *, call_id: UUID, job: str, provider: str, attempts: Sequence[LLMAttempt]) -> None:
        async with self._sessions.begin() as s:
            s.add_all(
                LLMCallRow(
                    call_id=call_id,
                    attempt=i,
                    job=job,
                    provider=provider,
                    model=a.model,
                    status=a.status,
                    http_code=a.http_code,
                    latency_ms=a.latency_ms,
                    tokens_in=a.tokens_in,
                    tokens_out=a.tokens_out,
                )
                for i, a in enumerate(attempts, start=1)
            )


@dataclass(frozen=True)
class UsageRow:
    day: date
    model: str
    status: str
    requests: int
    tokens_in: int
    tokens_out: int


async def usage(sessions: async_sessionmaker[AsyncSession], *, days: int = 7) -> list[UsageRow]:
    """Requests per UTC day, model and status over the last `days` days, newest day first."""
    since = datetime.now(UTC) - timedelta(days=days)
    day = cast(func.timezone("UTC", LLMCallRow.created_at), Date)
    query = (
        select(
            day,
            LLMCallRow.model,
            LLMCallRow.status,
            func.count(),
            func.coalesce(func.sum(LLMCallRow.tokens_in), 0),
            func.coalesce(func.sum(LLMCallRow.tokens_out), 0),
        )
        .where(LLMCallRow.created_at >= since)
        .group_by(day, LLMCallRow.model, LLMCallRow.status)
        .order_by(day.desc(), LLMCallRow.model, LLMCallRow.status)
    )
    async with sessions() as s:
        rows = (await s.execute(query)).all()
    return [UsageRow(r[0], r[1], r[2], int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)) for r in rows]
