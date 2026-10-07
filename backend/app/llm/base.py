from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

type AttemptStatus = Literal[
    "ok", "rate_limited", "quota_exhausted", "unavailable", "invalid_response", "error"
]


class LLMAttempt(BaseModel):
    """One request to one model. Failed attempts count too: they use up the free-tier quota."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    status: AttemptStatus
    http_code: int | None = None
    latency_ms: int
    tokens_in: int | None = None
    tokens_out: int | None = None
    message: str | None = None


class LLMResult[M: BaseModel](BaseModel):
    """A validated structured reply, plus every attempt it took (for the run log and the benchmark)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: M
    model: str
    attempts: list[LLMAttempt]


class LLMError(Exception):
    """The provider could not produce a valid reply. `attempts` says what was tried."""

    def __init__(self, message: str, attempts: list[LLMAttempt] | None = None) -> None:
        super().__init__(message)
        self.attempts = attempts or []


class LLMRateLimitedError(LLMError):
    """Every model is out of quota (429). A benchmark records this as `quota`, not as an agent failure."""


class LLMUnavailableError(LLMError):
    """No model gave a valid reply (server errors, invalid replies, or a mix with quota errors)."""


class LLMProvider(Protocol):
    """One interface for every LLM call (docs/architecture.md §4). Gemini in real runs, Fake in tests."""

    async def generate[M: BaseModel](self, *, system: str, prompt: str, schema: type[M]) -> LLMResult[M]:
        """Return a reply that validates against `schema`.

        `system` holds trusted instructions only. Untrusted page content belongs in `prompt`, inside clearly
        delimited blocks (AGENTS.md §4).
        """
        ...
