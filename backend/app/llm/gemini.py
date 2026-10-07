import asyncio
import random
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMAttempt, LLMError, LLMRateLimitedError, LLMResult, LLMUnavailableError

# Tried in this order (docs/research/phase-0-vishwas-gemini-structured-output.md). Each model has its own
# free-tier quota (5 requests/min, 20/day per project), so the chain also triples the daily budget.
DEFAULT_MODELS: tuple[str, ...] = ("gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash")

_SERVER_ERRORS = frozenset({500, 502, 503, 504})
_DELAY = re.compile(r"^(\d+(?:\.\d+)?)s$")

type Sleep = Callable[[float], Awaitable[None]]
type Clock = Callable[[], float]


class RateLimiter:
    """Keeps each model under `per_minute` requests in any 60 s window, so we rarely hit a 429 at all."""

    def __init__(
        self, per_minute: int = 5, *, sleep: Sleep = asyncio.sleep, clock: Clock = time.monotonic
    ) -> None:
        self._per_minute = per_minute
        self._sleep = sleep
        self._clock = clock
        self._calls: dict[str, deque[float]] = {}

    async def wait(self, model: str) -> None:
        calls = self._calls.setdefault(model, deque())
        now = self._clock()
        while calls and now - calls[0] >= 60:
            calls.popleft()
        if len(calls) >= self._per_minute:
            await self._sleep(60 - (now - calls[0]))
            calls.popleft()
        calls.append(self._clock())


class GeminiProvider:
    """Gemini with structured output, our own retry rules and a model fallback chain.

    - per-minute 429: wait the server's `retryDelay`, retry the same model (at most `max_rate_retries` times)
    - per-day 429: move to the next model at once
    - 500/502/503/504: one retry with backoff, then the next model
    - no answer within `timeout_s`: the next model (retrying a stall would cost another `timeout_s`)
    - reply that doesn't validate against the schema: the next model
    - any other error (bad key, bad request): raise at once, since another model won't fix it
    """

    def __init__(
        self,
        api_key: str,
        models: Sequence[str] = DEFAULT_MODELS,
        *,
        client: Any = None,
        sleep: Sleep = asyncio.sleep,
        limiter: RateLimiter | None = None,
        max_rate_wait_s: float = 60.0,
        max_rate_retries: int = 2,
        server_retry_delay_s: float = 2.0,
        timeout_s: float = 60.0,
    ) -> None:
        if not models:
            raise ValueError("GeminiProvider needs at least one model")
        if client is None and not api_key:
            raise LLMError("GEMINI_API_KEY is empty; set it in the repo-root .env")
        self._models = list(models)
        self._client = client if client is not None else genai.Client(api_key=api_key)
        self._sleep = sleep
        self._limiter = limiter if limiter is not None else RateLimiter(sleep=sleep)
        self._max_rate_wait_s = max_rate_wait_s
        self._max_rate_retries = max_rate_retries
        self._server_retry_delay_s = server_retry_delay_s
        # The SDK has no timeout by default; one stalled request hung a run for over 10 minutes.
        self._timeout_s = timeout_s

    async def generate[M: BaseModel](self, *, system: str, prompt: str, schema: type[M]) -> LLMResult[M]:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            response_mime_type="application/json",
            # Not `response_schema`: it rejects our extra="forbid" models (additionalProperties: false).
            response_json_schema=schema.model_json_schema(),
        )
        attempts: list[LLMAttempt] = []
        for model in self._models:
            rate_retries = server_retries = 0
            while True:
                await self._limiter.wait(model)
                t0 = time.perf_counter()
                try:
                    async with asyncio.timeout(self._timeout_s):
                        response = await self._client.aio.models.generate_content(
                            model=model, contents=prompt, config=config
                        )
                except TimeoutError:
                    attempts.append(
                        LLMAttempt(
                            model=model,
                            status="unavailable",
                            latency_ms=_ms_since(t0),
                            message=f"no answer within {self._timeout_s:g} s",
                        )
                    )
                    break
                except errors.APIError as e:
                    ms = _ms_since(t0)
                    if e.code == 429 and not _is_daily_quota(e) and rate_retries < self._max_rate_retries:
                        attempts.append(_attempt(model, "rate_limited", e, ms))
                        rate_retries += 1
                        await self._sleep(min(_retry_delay(e) or 10.0, self._max_rate_wait_s))
                        continue
                    if e.code == 429:
                        attempts.append(_attempt(model, "quota_exhausted", e, ms))
                        break
                    if e.code in _SERVER_ERRORS:
                        attempts.append(_attempt(model, "unavailable", e, ms))
                        if server_retries < 1:
                            server_retries += 1
                            await self._sleep(self._server_retry_delay_s * (1 + random.random()))
                            continue
                        break
                    attempts.append(_attempt(model, "error", e, ms))
                    raise LLMError(f"Gemini rejected the request: {e.code} {e.status}", attempts) from e

                usage = response.usage_metadata
                tokens_in = usage.prompt_token_count if usage else None
                tokens_out = usage.candidates_token_count if usage else None
                try:
                    value = schema.model_validate_json(response.text or "")
                except ValidationError as e:
                    attempts.append(
                        LLMAttempt(
                            model=model,
                            status="invalid_response",
                            latency_ms=_ms_since(t0),
                            tokens_in=tokens_in,
                            tokens_out=tokens_out,
                            message=str(e).splitlines()[0][:300],
                        )
                    )
                    break
                attempts.append(
                    LLMAttempt(
                        model=model,
                        status="ok",
                        http_code=200,
                        latency_ms=_ms_since(t0),
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                    )
                )
                return LLMResult[M](value=value, model=model, attempts=attempts)

        if attempts and all(a.status in ("rate_limited", "quota_exhausted") for a in attempts):
            raise LLMRateLimitedError("every Gemini model is out of quota", attempts)
        raise LLMUnavailableError("no Gemini model returned a valid reply", attempts)


def _ms_since(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def _attempt(model: str, status: Any, e: errors.APIError, ms: int) -> LLMAttempt:
    return LLMAttempt(
        model=model, status=status, http_code=e.code, latency_ms=ms, message=(e.message or "")[:300]
    )


def _error_details(e: errors.APIError) -> list[dict[str, Any]]:
    body = e.details if isinstance(e.details, dict) else {}
    error = body.get("error", body)
    details = error.get("details", []) if isinstance(error, dict) else []
    return [d for d in details if isinstance(d, dict)]


def _retry_delay(e: errors.APIError) -> float | None:
    """`RetryInfo.retryDelay` (e.g. "9s"), which the SDK itself ignores."""
    for d in _error_details(e):
        if d.get("@type", "").endswith("RetryInfo"):
            match = _DELAY.match(str(d.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None


def _is_daily_quota(e: errors.APIError) -> bool:
    for d in _error_details(e):
        if d.get("@type", "").endswith("QuotaFailure"):
            for violation in d.get("violations", []):
                if "PerDay" in str(violation.get("quotaId", "")):
                    return True
    return False
