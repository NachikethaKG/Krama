import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMAttempt, LLMError, LLMResult, LLMUnavailableError

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"


class OllamaProvider:
    """A local model through Ollama's `/api/chat`, for development only (ADR 0010).

    Opt-in with `LLM_PROVIDER=ollama`; Gemini stays the default and CI uses the fake provider. Structured
    output goes through Ollama's `format` (the reply is constrained to the JSON schema), with temperature 0.

    - text only: a call with an image raises `LLMError` at once; callers fall back as they do without vision
    - Ollama not running, or no answer within `timeout_s`: `LLMUnavailableError` with a clear message
    - a model that isn't pulled, or any other error answer: `LLMError` (retrying won't fix it)
    - a reply that doesn't validate against the schema: one more try, then `LLMUnavailableError`

    `num_ctx` is set on every call: Ollama's default context (4096 tokens) silently cuts long prompts.
    """

    def __init__(
        self,
        url: str = DEFAULT_URL,
        model: str = DEFAULT_MODEL,
        *,
        timeout_s: float = 180.0,
        num_ctx: int = 8192,
        max_invalid_retries: int = 1,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model:
            raise ValueError("OllamaProvider needs a model name")
        self._url = url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._num_ctx = num_ctx
        self._max_invalid_retries = max_invalid_retries
        self._client = client

    async def generate[M: BaseModel](
        self, *, system: str, prompt: str, schema: type[M], image: bytes | None = None
    ) -> LLMResult[M]:
        if image is not None:
            raise LLMError(f"the local model {self._model} is text only; vision calls need Gemini")
        body: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "format": schema.model_json_schema(),
            "options": {"temperature": 0, "num_ctx": self._num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        attempts: list[LLMAttempt] = []
        for _ in range(1 + self._max_invalid_retries):
            t0 = time.perf_counter()
            try:
                response = await self._post(body)
            except httpx.TimeoutException as e:
                waited = f"no answer within {self._timeout_s:g} s"
                attempts.append(self._attempt("unavailable", t0, message=waited))
                raise LLMUnavailableError(
                    f"Ollama ({self._model}) gave no answer within {self._timeout_s:g} s", attempts
                ) from e
            except httpx.TransportError as e:
                failed = f"connection failed: {type(e).__name__}"
                attempts.append(self._attempt("unavailable", t0, message=failed))
                raise LLMUnavailableError(
                    f"Ollama is not reachable at {self._url}. Start it (`ollama serve`) or set LLM_PROVIDER.",
                    attempts,
                ) from e

            if response.status_code != 200:
                message = _error_text(response)
                attempts.append(self._attempt("error", t0, http_code=response.status_code, message=message))
                if response.status_code == 404:
                    message = f"{message}. Pull it first: ollama pull {self._model}"
                raise LLMError(f"Ollama rejected the request: {response.status_code} {message}", attempts)

            data = response.json()
            tokens_in, tokens_out = data.get("prompt_eval_count"), data.get("eval_count")
            text = (data.get("message") or {}).get("content") or ""
            try:
                value = schema.model_validate_json(text)
            except ValidationError as e:
                attempts.append(
                    self._attempt(
                        "invalid_response",
                        t0,
                        http_code=200,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        message=str(e).splitlines()[0][:300],
                    )
                )
                continue
            attempts.append(
                self._attempt("ok", t0, http_code=200, tokens_in=tokens_in, tokens_out=tokens_out)
            )
            return LLMResult[M](value=value, model=self._model, attempts=attempts)
        raise LLMUnavailableError(f"Ollama ({self._model}) gave no reply that fits the schema", attempts)

    async def _post(self, body: dict[str, Any]) -> httpx.Response:
        url = f"{self._url}/api/chat"
        if self._client is not None:
            return await self._client.post(url, json=body, timeout=self._timeout_s)
        async with httpx.AsyncClient() as client:
            return await client.post(url, json=body, timeout=self._timeout_s)

    def _attempt(
        self,
        status: Any,
        t0: float,
        *,
        http_code: int | None = None,
        tokens_in: int | None = None,
        tokens_out: int | None = None,
        message: str | None = None,
    ) -> LLMAttempt:
        return LLMAttempt(
            model=self._model,
            status=status,
            http_code=http_code,
            latency_ms=round((time.perf_counter() - t0) * 1000),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            message=message,
        )


def _error_text(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
    except ValueError:
        error = None
    return str(error or response.text or response.reason_phrase)[:300]
