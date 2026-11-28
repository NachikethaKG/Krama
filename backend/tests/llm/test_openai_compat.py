"""The OpenAI-compatible provider (Groq) against a fake server: structured output, fallbacks and limits."""

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from app.llm import LLMError, LLMRateLimitedError, LLMResult, LLMUnavailableError
from app.llm.openai_compat import OpenAICompatProvider, SplitProvider

pytestmark = pytest.mark.anyio


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool


def reply(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 3},
        },
    )


def limited(message: str) -> httpx.Response:
    return httpx.Response(429, json={"error": {"message": message, "code": "rate_limit_exceeded"}})


PER_MINUTE = "Rate limit reached on tokens per minute (TPM): Limit 8000. Please try again in 2.5s."
PER_DAY = "Rate limit reached on requests per day (RPD): Limit 1000. Please try again in 1h2m."


def provider(
    *answers: httpx.Response, models: tuple[str, ...] = ("a", "b")
) -> tuple[Any, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0)

    slept: list[float] = []

    async def sleep(s: float) -> None:
        slept.append(s)

    llm = OpenAICompatProvider(
        "https://llm.test/v1", "key", models, client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
        sleep=sleep,
    )  # fmt: skip
    llm.slept = slept  # type: ignore[attr-defined]
    return llm, sent


async def ask(llm: Any) -> LLMResult[Answer]:
    result: LLMResult[Answer] = await llm.generate(system="Be brief.", prompt="Ok?", schema=Answer)
    return result


async def test_a_reply_is_validated_against_the_schema() -> None:
    llm, sent = provider(reply('{"ok": true}'))

    result = await ask(llm)

    assert result.value.ok and result.model == "a"
    assert sent[0]["response_format"]["type"] == "json_schema"
    assert sent[0]["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert [(a.status, a.tokens_in) for a in result.attempts] == [("ok", 9)]


async def test_a_model_without_json_schema_gets_a_json_object_with_the_schema_in_the_prompt() -> None:
    rejected = httpx.Response(
        400, json={"error": {"message": "response_format json_schema is not supported"}}
    )
    llm, sent = provider(rejected, reply('{"ok": false}'))

    result = await ask(llm)

    assert result.value.ok is False
    assert sent[1]["response_format"] == {"type": "json_object"}
    assert '"ok"' in sent[1]["messages"][0]["content"]


async def test_a_reply_that_doesnt_fit_gets_one_more_try() -> None:
    llm, _ = provider(reply('{"ok": "maybe"}'), reply('{"ok": true}'))

    result = await ask(llm)

    assert [a.status for a in result.attempts] == ["invalid_response", "ok"]


async def test_the_per_minute_limit_moves_on_and_is_not_the_days_quota() -> None:
    llm, _ = provider(limited(PER_MINUTE), reply('{"ok": true}'))

    result = await ask(llm)

    assert result.model == "b"
    assert result.attempts[0].status == "rate_limited"


async def test_when_every_model_is_busy_it_waits_once_and_tries_again() -> None:
    llm, _ = provider(limited(PER_MINUTE), limited(PER_MINUTE), reply('{"ok": true}'))

    result = await ask(llm)

    assert llm.slept == [2.5] and result.model == "a"


async def test_every_model_out_of_its_daily_quota_is_a_rate_limit_error() -> None:
    llm, _ = provider(limited(PER_DAY), limited(PER_DAY))

    with pytest.raises(LLMRateLimitedError) as e:
        await ask(llm)

    assert [a.status for a in e.value.attempts] == ["quota_exhausted", "quota_exhausted"]


async def test_server_errors_move_on_then_give_up() -> None:
    llm, _ = provider(httpx.Response(503), httpx.Response(500))

    with pytest.raises(LLMUnavailableError):
        await ask(llm)


async def test_a_bad_key_raises_at_once() -> None:
    llm, sent = provider(httpx.Response(401, json={"error": {"message": "Invalid API Key"}}))

    with pytest.raises(LLMError, match="Invalid API Key"):
        await ask(llm)
    assert len(sent) == 1


async def test_images_go_to_the_vision_provider() -> None:
    text, _ = provider(reply('{"ok": false}'))
    seen: list[bytes | None] = []

    class Vision:
        async def generate(self, *, system: str, prompt: str, schema: Any, image: bytes | None = None) -> Any:
            seen.append(image)
            return LLMResult[Answer](value=Answer(ok=True), model="gemini", attempts=[])

    split = SplitProvider(text, Vision())

    assert (await split.generate(system="s", prompt="p", schema=Answer, image=b"png")).value.ok
    assert (await split.generate(system="s", prompt="p", schema=Answer)).value.ok is False
    assert seen == [b"png"]
    with pytest.raises(LLMError, match="vision"):
        await SplitProvider(text, None).generate(system="s", prompt="p", schema=Answer, image=b"png")


async def test_a_big_page_waits_for_the_per_minute_budget_more_than_once() -> None:
    # Wiktionary, 2026-11-28: a 6,000-token page made every model 429 twice in a row; one wait wasn't enough.
    busy = [limited(PER_MINUTE), limited(PER_MINUTE)]
    llm, _ = provider(*busy, *busy, *busy, reply('{"ok": true}'))

    result = await ask(llm)

    assert llm.slept == [2.5, 2.5, 2.5] and result.value.ok


async def test_it_gives_up_after_the_wait_budget() -> None:
    llm, _ = provider(*[limited(PER_MINUTE)] * 60)

    with pytest.raises(LLMUnavailableError):
        await ask(llm)
    assert sum(llm.slept) <= 60


def test_groq_sees_a_smaller_page() -> None:
    # Groq's free tier caps one request at 8,000 tokens; the Internet Archive's page made 9,000+ (#482).
    from app.config import Settings

    assert Settings(_env_file=None, llm_provider="groq").page_budget == 14_000
    assert Settings(_env_file=None, llm_provider="gemini").page_budget == 24_000
    assert Settings(_env_file=None, llm_provider="groq", page_budget_chars=9_000).page_budget == 9_000
