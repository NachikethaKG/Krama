import asyncio
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors
from pydantic import BaseModel

from app.contracts_gen.plan_schema import PlannedStep


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class PlanOut(BaseModel):
    """Stand-in for the planner's LLM output (#35): just the steps, taken unchanged from the contract."""

    steps: list[PlannedStep]


def ok(text: str, tokens_in: int = 700, tokens_out: int = 600) -> SimpleNamespace:
    usage = SimpleNamespace(prompt_token_count=tokens_in, candidates_token_count=tokens_out)
    return SimpleNamespace(text=text, usage_metadata=usage)


def rate_limited(*, per_day: bool = False, retry_delay: str | None = "9s") -> errors.ClientError:
    """A 429 shaped like the real one recorded in the #25 research."""
    quota_id = (
        "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
        if per_day
        else ("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")
    )
    details: list[dict[str, Any]] = [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id}]}
    ]
    if retry_delay is not None:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay})
    body = {
        "error": {
            "code": 429,
            "message": "quota exceeded",
            "status": "RESOURCE_EXHAUSTED",
            "details": details,
        }
    }
    return errors.ClientError(429, body)


def server_error(code: int = 503) -> errors.ServerError:
    body = {"error": {"code": code, "message": "high demand", "status": "UNAVAILABLE"}}
    return errors.ServerError(code, body)


def bad_key() -> errors.ClientError:
    body = {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}}
    return errors.ClientError(400, body)


HANG = object()
"""A scripted outcome for a request that never answers."""


@dataclass
class FakeGenaiClient:
    """Mimics `genai.Client().aio.models.generate_content`: each call pops the next scripted outcome."""

    outcomes: list[Any]
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model: str, contents: str, config: Any) -> Any:
        self.calls.append((model, config))
        outcome = self.outcomes.pop(0)
        if outcome is HANG:
            await asyncio.sleep(3600)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    @property
    def models_called(self) -> list[str]:
        return [m for m, _ in self.calls]


@dataclass
class FakeSleep:
    slept: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)
