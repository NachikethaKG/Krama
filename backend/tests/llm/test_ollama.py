import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.llm import (
    LLMError,
    LLMProvider,
    LLMUnavailableError,
    OllamaProvider,
    create_provider,
)
from tests.llm.conftest import PlanOut

pytestmark = pytest.mark.anyio

FIXTURE = Path(__file__).parents[1] / "llm_fixtures" / "gitea-create-repo-plan.json"
PLAN_JSON = json.dumps(json.loads(FIXTURE.read_text(encoding="utf-8"))["response"])

type Handler = Callable[[httpx.Request], httpx.Response]


class FakeOllama:
    """A scripted stand-in for Ollama's HTTP API: each request gets the next handler's response."""

    def __init__(self, *handlers: Handler) -> None:
        self.handlers = list(handlers)
        self.requests: list[dict[str, Any]] = []
        self.urls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.urls.append(str(request.url))
        self.requests.append(json.loads(request.content))
        return self.handlers.pop(0)(request)

    def provider(self, **kwargs: Any) -> OllamaProvider:
        client = httpx.AsyncClient(transport=httpx.MockTransport(self))
        return OllamaProvider("http://127.0.0.1:11434/", "qwen2.5:7b", client=client, **kwargs)


def chat(content: str, tokens_in: int = 900, tokens_out: int = 300) -> Handler:
    body = {
        "model": "qwen2.5:7b",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": tokens_in,
        "eval_count": tokens_out,
    }
    return lambda _: httpx.Response(200, json=body)


def error(code: int, message: str) -> Handler:
    return lambda _: httpx.Response(code, json={"error": message})


def raises(exc: Exception) -> Handler:
    def handler(_: httpx.Request) -> httpx.Response:
        raise exc

    return handler


async def test_valid_reply() -> None:
    server = FakeOllama(chat(PLAN_JSON))
    p: LLMProvider = server.provider()

    result = await p.generate(system="plan it", prompt="create demo-repo", schema=PlanOut)

    assert len(result.value.steps) == 4
    assert result.model == "qwen2.5:7b"
    assert [(a.status, a.http_code, a.tokens_in, a.tokens_out) for a in result.attempts] == [
        ("ok", 200, 900, 300)
    ]


async def test_request_shape() -> None:
    server = FakeOllama(chat(PLAN_JSON))

    await server.provider(num_ctx=16384).generate(system="plan it", prompt="create demo-repo", schema=PlanOut)

    assert server.urls == ["http://127.0.0.1:11434/api/chat"]
    body = server.requests[0]
    assert body["model"] == "qwen2.5:7b"
    assert body["stream"] is False
    assert body["format"] == PlanOut.model_json_schema()
    assert body["options"] == {"temperature": 0, "num_ctx": 16384}
    # Trusted instructions and the (possibly untrusted) prompt stay in separate messages.
    assert body["messages"] == [
        {"role": "system", "content": "plan it"},
        {"role": "user", "content": "create demo-repo"},
    ]


async def test_invalid_reply_is_retried_once() -> None:
    server = FakeOllama(chat('{"steps": "nope"}'), chat(PLAN_JSON))

    result = await server.provider().generate(system="s", prompt="p", schema=PlanOut)

    assert [a.status for a in result.attempts] == ["invalid_response", "ok"]
    assert len(server.requests) == 2


async def test_invalid_twice_is_unavailable() -> None:
    server = FakeOllama(chat("not json"), chat("{}"))

    with pytest.raises(LLMUnavailableError, match="fits the schema") as e:
        await server.provider().generate(system="s", prompt="p", schema=PlanOut)

    assert [a.status for a in e.value.attempts] == ["invalid_response", "invalid_response"]


async def test_not_running_says_how_to_fix_it() -> None:
    server = FakeOllama(raises(httpx.ConnectError("refused")))

    with pytest.raises(LLMUnavailableError, match=re.escape("not reachable at http://127.0.0.1:11434")) as e:
        await server.provider().generate(system="s", prompt="p", schema=PlanOut)

    assert [(a.status, a.message) for a in e.value.attempts] == [
        ("unavailable", "connection failed: ConnectError")
    ]


async def test_timeout_is_unavailable_without_a_retry() -> None:
    server = FakeOllama(raises(httpx.ReadTimeout("slow")))

    with pytest.raises(LLMUnavailableError, match="no answer within 5 s"):
        await server.provider(timeout_s=5).generate(system="s", prompt="p", schema=PlanOut)

    assert len(server.requests) == 1


async def test_missing_model_says_to_pull_it() -> None:
    server = FakeOllama(error(404, "model 'qwen2.5:7b' not found"))

    with pytest.raises(LLMError, match=re.escape("ollama pull qwen2.5:7b")) as e:
        await server.provider().generate(system="s", prompt="p", schema=PlanOut)

    assert not isinstance(e.value, LLMUnavailableError)
    assert [(a.status, a.http_code) for a in e.value.attempts] == [("error", 404)]


async def test_server_error_is_not_retried() -> None:
    server = FakeOllama(error(500, "out of memory"))

    with pytest.raises(LLMError, match="500 out of memory"):
        await server.provider().generate(system="s", prompt="p", schema=PlanOut)

    assert len(server.requests) == 1


async def test_image_is_refused_without_a_request() -> None:
    server = FakeOllama()

    with pytest.raises(LLMError, match="text only"):
        await server.provider().generate(system="s", prompt="p", schema=PlanOut, image=b"\x89PNG")

    assert server.requests == []


def test_settings_select_ollama() -> None:
    settings = Settings(
        llm_provider="ollama", ollama_url="http://127.0.0.1:9999", ollama_model="llama3:8b", _env_file=None
    )

    provider = create_provider(settings)

    assert isinstance(provider, OllamaProvider)
    assert provider._url == "http://127.0.0.1:9999"
    assert provider._model == "llama3:8b"
