"""LLM usage rows (#464): one per attempt, summed per day, model and status."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.llm_calls import DbCallSink, usage
from app.db.models import LLMCallRow
from app.llm import LLMAttempt
from app.llm_usage_cli import format_usage

pytestmark = pytest.mark.anyio


async def test_attempts_are_stored_and_summed(sessions: async_sessionmaker[AsyncSession]) -> None:
    sink = DbCallSink(sessions)
    busy = LLMAttempt(model="gemini-3.8-flash", status="unavailable", http_code=503, latency_ms=8000)
    ok = LLMAttempt(model="gemini-2.5-flash", status="ok", latency_ms=900, tokens_in=1200, tokens_out=300)
    call = uuid4()

    await sink.record(call_id=call, job="LLMPlan", provider="gemini", attempts=[busy, ok])
    await sink.record(call_id=uuid4(), job="TaskAnswer", provider="gemini", attempts=[ok])

    async with sessions() as s:
        rows = list(await s.scalars(select(LLMCallRow).where(LLMCallRow.call_id == call).order_by("attempt")))
    assert [(r.attempt, r.model, r.status, r.http_code) for r in rows] == [
        (1, "gemini-3.8-flash", "unavailable", 503),
        (2, "gemini-2.5-flash", "ok", None),
    ]

    report = await usage(sessions, days=1)
    by_model = {(r.model, r.status): (r.requests, r.tokens_in, r.tokens_out) for r in report}
    assert by_model == {
        ("gemini-2.5-flash", "ok"): (2, 2400, 600),
        ("gemini-3.8-flash", "unavailable"): (1, 0, 0),
    }
    text = format_usage(report)
    assert "gemini-2.5-flash" in text and "2 requests (ok 2)" in text
