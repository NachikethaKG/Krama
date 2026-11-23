"""Record every LLM request (#464): which job, which model, how it went, how long, how many tokens.

The free-tier limits we plan around were measured long ago and have drifted (spike #457:
gemini-2.5-flash answered 27 requests in a day without a 429, while 3.8-flash answered 503 all day).
Recording each attempt lets the benchmark and the gate plan on measured numbers. Prompts and replies are
never recorded: they hold page text.
"""

import logging
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel

from app.llm.base import LLMAttempt, LLMError, LLMProvider, LLMResult

logger = logging.getLogger(__name__)


class CallSink(Protocol):
    """Where the attempts of one call go (the database in the API and the worker)."""

    async def record(
        self, *, call_id: UUID, job: str, provider: str, attempts: Sequence[LLMAttempt]
    ) -> None: ...


class RecordingProvider:
    """Wraps a provider; each call's attempts go to `sink`, whether the call worked or not.

    A sink that fails is logged and ignored: losing a usage row must never fail a run.
    """

    def __init__(self, inner: LLMProvider, sink: CallSink, *, provider: str) -> None:
        self._inner = inner
        self._sink = sink
        self._provider = provider

    async def generate[M: BaseModel](
        self, *, system: str, prompt: str, schema: type[M], image: bytes | None = None
    ) -> LLMResult[M]:
        try:
            result = await self._inner.generate(system=system, prompt=prompt, schema=schema, image=image)
        except LLMError as e:
            await self._record(schema.__name__, e.attempts)
            raise
        await self._record(schema.__name__, result.attempts)
        return result

    async def _record(self, job: str, attempts: Sequence[LLMAttempt]) -> None:
        if not attempts:
            return
        try:
            await self._sink.record(call_id=uuid4(), job=job, provider=self._provider, attempts=attempts)
        except Exception:
            logger.warning("could not record an LLM call for %s", job, exc_info=True)
