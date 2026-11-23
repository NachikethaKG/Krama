"""Every LLM request is recorded (#464), without failing the call when recording fails."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel

from app.llm import LLMAttempt, LLMResult, LLMUnavailableError
from app.llm.recording import RecordingProvider

pytestmark = pytest.mark.anyio


class Reply(BaseModel):
    ok: bool


OK = LLMAttempt(model="m2", status="ok", http_code=200, latency_ms=900, tokens_in=10, tokens_out=3)
BUSY = LLMAttempt(model="m1", status="unavailable", http_code=503, latency_ms=8000)


class Scripted:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome

    async def generate(self, **_: Any) -> Any:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class Sink:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str, list[LLMAttempt]]] = []
        self.fail = fail

    async def record(self, *, call_id: UUID, job: str, provider: str, attempts: Sequence[LLMAttempt]) -> None:
        if self.fail:
            raise RuntimeError("database down")
        self.calls.append((job, provider, list(attempts)))


async def test_a_call_records_every_attempt_with_its_job() -> None:
    sink = Sink()
    result = LLMResult[Reply](value=Reply(ok=True), model="m2", attempts=[BUSY, OK])
    provider = RecordingProvider(Scripted(result), sink, provider="gemini")

    got = await provider.generate(system="s", prompt="p", schema=Reply)

    assert got.value.ok
    assert sink.calls == [("Reply", "gemini", [BUSY, OK])]


async def test_a_failed_call_is_recorded_and_still_raises() -> None:
    sink = Sink()
    provider = RecordingProvider(Scripted(LLMUnavailableError("down", [BUSY])), sink, provider="gemini")

    with pytest.raises(LLMUnavailableError):
        await provider.generate(system="s", prompt="p", schema=Reply)

    assert sink.calls == [("Reply", "gemini", [BUSY])]


async def test_a_broken_sink_never_fails_the_call() -> None:
    result = LLMResult[Reply](value=Reply(ok=True), model="m2", attempts=[OK])
    provider = RecordingProvider(Scripted(result), Sink(fail=True), provider="ollama")

    assert (await provider.generate(system="s", prompt="p", schema=Reply)).value.ok
