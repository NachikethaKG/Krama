"""Any OpenAI-compatible chat API (Groq first; Cloudflare, OpenRouter and GitHub Models speak it too).

A spike for the Phase 7 gate (#482): Gemini's free tier gave about 20 requests a day, while Groq's free tier
gives 1,000 a day per model (checked from its rate-limit headers, 2026-11-28). Opt-in with
`LLM_PROVIDER=groq`; Gemini stays the default until an ADR says otherwise.
"""

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import (
    AttemptStatus,
    LLMAttempt,
    LLMError,
    LLMProvider,
    LLMRateLimitedError,
    LLMResult,
    LLMUnavailableError,
)

GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_MODELS: tuple[str, ...] = ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b")

_SERVER_ERRORS = frozenset({500, 502, 503, 504})
_PER_DAY = re.compile(r"per day|\((?:RPD|TPD)\)", re.IGNORECASE)
_TRY_AGAIN = re.compile(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", re.IGNORECASE)

type Sleep = Callable[[float], Awaitable[None]]


class OpenAICompatProvider:
    """Structured output from an OpenAI-compatible API, with a model fallback chain like `GeminiProvider`.

    - JSON: `response_format` `json_schema` first; a model that rejects it gets `json_object` with the schema
      in the system prompt (remembered per model)
    - a reply that doesn't validate: one more try on the same model, then the next model
    - per-day 429 (requests or tokens per day): the next model; the attempt is `quota_exhausted`
    - per-minute 429 (Groq: 8,000 tokens a minute per model): the next model; after all of them, one wait of
      the shortest "try again in" (at most `max_rate_wait_s`) and one more round. Recorded as `rate_limited`,
      so a benchmark never counts it as the day's quota.
    - 5xx, a timeout or a dropped connection: the next model
    - any other error (bad key, bad request): raise at once
    - text only: an image raises `LLMError` (`SplitProvider` sends images elsewhere)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        models: Sequence[str],
        *,
        name: str = "groq",
        timeout_s: float = 60.0,
        max_rate_wait_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if not models:
            raise ValueError("OpenAICompatProvider needs at least one model")
        if client is None and not api_key:
            raise LLMError(f"The {name} API key is empty; set it in the repo-root .env")
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._models = list(models)
        self._name = name
        self._timeout_s = timeout_s
        self._max_rate_wait_s = max_rate_wait_s
        self._client = client
        self._sleep = sleep
        self._json_object_only: set[str] = set()

    async def generate[M: BaseModel](
        self, *, system: str, prompt: str, schema: type[M], image: bytes | None = None
    ) -> LLMResult[M]:
        if image is not None:
            raise LLMError(f"{self._name} is used for text only here; vision calls go to Gemini")
        attempts: list[LLMAttempt] = []
        waits: list[float] = []
        for round_ in range(2):
            for model in self._models:
                value = await self._try_model(model, system, prompt, schema, attempts, waits)
                if value is not None:
                    return LLMResult[M](value=value, model=model, attempts=attempts)
            if round_ == 0 and waits and min(waits) <= self._max_rate_wait_s:
                await self._sleep(min(waits))
                waits.clear()
                continue
            break
        if attempts and all(a.status == "quota_exhausted" for a in attempts):
            raise LLMRateLimitedError(f"Every {self._name} model is out of its daily quota", attempts)
        raise LLMUnavailableError(f"No {self._name} model gave a valid reply", attempts)

    async def _try_model[M: BaseModel](
        self,
        model: str,
        system: str,
        prompt: str,
        schema: type[M],
        attempts: list[LLMAttempt],
        waits: list[float],
    ) -> M | None:
        for _ in range(2):  # a reply that doesn't fit the schema gets one more try
            body = self._body(model, system, prompt, schema)
            t0 = time.perf_counter()
            try:
                response = await self._post(body)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                attempts.append(_attempt(model, "unavailable", t0, message=type(e).__name__))
                return None
            code = response.status_code
            if code == 400 and "response_format" in response.text and model not in self._json_object_only:
                self._json_object_only.add(model)  # this model can't do json_schema: ask for a JSON object
                continue
            if code == 429:
                message = _error_text(response)
                daily = bool(_PER_DAY.search(message))
                status: AttemptStatus = "quota_exhausted" if daily else "rate_limited"
                attempts.append(_attempt(model, status, t0, http_code=429, message=message))
                if not daily:
                    waits.append(_retry_after(response, message))
                return None
            if code in _SERVER_ERRORS:
                attempts.append(
                    _attempt(model, "unavailable", t0, http_code=code, message=_error_text(response))
                )
                return None
            if code != 200:
                attempts.append(_attempt(model, "error", t0, http_code=code, message=_error_text(response)))
                raise LLMError(f"{self._name} rejected the request: {code} {_error_text(response)}", attempts)
            data = response.json()
            usage = data.get("usage") or {}
            tokens = {"tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens")}
            text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            try:
                value = schema.model_validate_json(text)
            except ValidationError as e:
                attempts.append(
                    _attempt(
                        model,
                        "invalid_response",
                        t0,
                        http_code=200,
                        message=str(e).splitlines()[0][:300],
                        **tokens,
                    )
                )
                continue
            attempts.append(_attempt(model, "ok", t0, http_code=200, **tokens))
            return value
        return None

    def _body(self, model: str, system: str, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        json_schema = schema.model_json_schema()
        if model in self._json_object_only:
            system = (
                f"{system}\n\nReply with one JSON object that validates against this JSON schema:\n"
                f"{json.dumps(json_schema)}"
            )
            response_format: dict[str, Any] = {"type": "json_object"}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": json_schema},
            }
        body: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": response_format,
        }
        if "gpt-oss" in model:
            body["reasoning_effort"] = "low"  # reasoning tokens count against the 8,000 tokens a minute
        return body

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._key}"}
        if self._client is not None:
            return await self._client.post(self._url, json=body, headers=headers, timeout=self._timeout_s)
        async with httpx.AsyncClient() as client:
            return await client.post(self._url, json=body, headers=headers, timeout=self._timeout_s)


class SplitProvider:
    """Text to one provider, images to another: Groq has no vision model on the free key, Gemini does."""

    def __init__(self, text: LLMProvider, vision: LLMProvider | None) -> None:
        self._text = text
        self._vision = vision

    async def generate[M: BaseModel](
        self, *, system: str, prompt: str, schema: type[M], image: bytes | None = None
    ) -> LLMResult[M]:
        if image is None:
            return await self._text.generate(system=system, prompt=prompt, schema=schema)
        if self._vision is None:
            raise LLMError("No vision provider is configured (set GEMINI_API_KEY)")
        return await self._vision.generate(system=system, prompt=prompt, schema=schema, image=image)


def _attempt(
    model: str,
    status: AttemptStatus,
    t0: float,
    *,
    http_code: int | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    message: str | None = None,
) -> LLMAttempt:
    return LLMAttempt(
        model=model,
        status=status,
        http_code=http_code,
        latency_ms=round((time.perf_counter() - t0) * 1000),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        message=message,
    )


def _retry_after(response: httpx.Response, message: str) -> float:
    """Seconds until the per-minute limit frees up: the `retry-after` header, else "try again in 1m2.5s"."""
    header = response.headers.get("retry-after")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    m = _TRY_AGAIN.search(message)
    return (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 10.0


def _error_text(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
    except ValueError:
        error = None
    if isinstance(error, dict):
        error = error.get("message")
    return str(error or response.text or response.reason_phrase)[:300]
