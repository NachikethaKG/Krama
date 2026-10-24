import json
import os
from pathlib import Path

import httpx
import pytest

from app.llm import (
    GeminiProvider,
    LLMError,
    LLMProvider,
    LLMRateLimitedError,
    LLMUnavailableError,
)
from app.llm.gemini import RateLimiter
from tests.llm.conftest import (
    HANG,
    FakeGenaiClient,
    FakeSleep,
    PlanOut,
    bad_key,
    ok,
    rate_limited,
    server_error,
)

pytestmark = pytest.mark.anyio

MODELS = ("m1", "m2", "m3")
FIXTURE = Path(__file__).parents[1] / "llm_fixtures" / "gitea-create-repo-plan.json"
PLAN_JSON = json.dumps(json.loads(FIXTURE.read_text(encoding="utf-8"))["response"])


def provider(client: FakeGenaiClient, sleep: FakeSleep) -> GeminiProvider:
    return GeminiProvider("unused", MODELS, client=client, sleep=sleep, limiter=RateLimiter(sleep=sleep))


async def generate(p: LLMProvider) -> PlanOut:
    result = await p.generate(system="plan it", prompt="create demo-repo", schema=PlanOut)
    return result.value


async def test_first_model_answers() -> None:
    client, sleep = FakeGenaiClient([ok(PLAN_JSON)]), FakeSleep()

    result = await provider(client, sleep).generate(system="sys", prompt="create demo-repo", schema=PlanOut)

    assert len(result.value.steps) == 4
    assert result.model == "m1"
    assert [(a.model, a.status, a.tokens_in, a.tokens_out) for a in result.attempts] == [
        ("m1", "ok", 700, 600)
    ]
    assert sleep.slept == []


async def test_structured_output_config() -> None:
    client, sleep = FakeGenaiClient([ok(PLAN_JSON)]), FakeSleep()

    await generate(provider(client, sleep))

    config = client.calls[0][1]
    assert config.system_instruction == "plan it"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == PlanOut.model_json_schema()
    assert config.response_schema is None  # rejects additionalProperties: false
    assert config.temperature == 0


async def test_text_only_prompt_is_sent_as_is() -> None:
    client, sleep = FakeGenaiClient([ok(PLAN_JSON)]), FakeSleep()

    await generate(provider(client, sleep))

    assert client.contents == ["create demo-repo"]


async def test_image_is_sent_as_a_png_part_before_the_prompt() -> None:
    client, sleep = FakeGenaiClient([ok(PLAN_JSON)]), FakeSleep()
    png = b"\x89PNG\r\n\x1a\nfake"

    await provider(client, sleep).generate(system="s", prompt="find it", schema=PlanOut, image=png)

    image, text = client.contents[0]
    assert (image.inline_data.mime_type, image.inline_data.data) == ("image/png", png)
    assert text == "find it"


async def test_server_error_retries_once_then_falls_back() -> None:
    client = FakeGenaiClient([server_error(500), server_error(502), ok(PLAN_JSON)])
    sleep = FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m1", "m2"]
    assert [a.status for a in result.attempts] == ["unavailable", "unavailable", "ok"]
    assert result.model == "m2"
    assert len(sleep.slept) == 1


async def test_an_overloaded_model_503_moves_on_at_once() -> None:
    # #101: retrying an overloaded model cost 15 s while the next one answered in 2-3 s.
    client, sleep = FakeGenaiClient([server_error(503), ok(PLAN_JSON)]), FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m2"] and sleep.slept == []
    assert result.model == "m2"


async def test_a_dropped_connection_retries_once_then_falls_back() -> None:
    dropped = httpx.ConnectError("TLS handshake failed")
    client = FakeGenaiClient([dropped, dropped, ok(PLAN_JSON)])
    sleep = FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m1", "m2"]
    assert [a.status for a in result.attempts] == ["unavailable", "unavailable", "ok"]
    assert result.attempts[0].message == "connection failed: ConnectError"
    assert len(sleep.slept) == 1


async def test_no_connection_at_all_raises_unavailable_not_a_crash() -> None:
    client = FakeGenaiClient([httpx.ReadError("connection reset")] * 6)

    with pytest.raises(LLMUnavailableError):
        await provider(client, FakeSleep()).generate(system="s", prompt="p", schema=PlanOut)


async def test_per_minute_429_waits_retry_delay_and_retries_same_model() -> None:
    client = FakeGenaiClient([rate_limited(retry_delay="9s"), ok(PLAN_JSON)])
    sleep = FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m1"]
    assert sleep.slept == [9.0]
    assert [a.status for a in result.attempts] == ["rate_limited", "ok"]


async def test_per_minute_429_gives_up_on_model_after_max_retries() -> None:
    client = FakeGenaiClient([rate_limited(), rate_limited(), rate_limited(), ok(PLAN_JSON)])
    sleep = FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m1", "m1", "m2"]
    assert result.model == "m2"


async def test_per_day_429_moves_to_next_model_without_waiting() -> None:
    client = FakeGenaiClient([rate_limited(per_day=True), ok(PLAN_JSON)])
    sleep = FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m2"]
    assert sleep.slept == []
    assert result.attempts[0].status == "quota_exhausted"


async def test_invalid_reply_moves_to_next_model() -> None:
    client = FakeGenaiClient([ok('{"steps": [{"seq": "not a number"}]}'), ok(PLAN_JSON)])
    sleep = FakeSleep()

    result = await provider(client, sleep).generate(system="s", prompt="p", schema=PlanOut)

    assert [a.status for a in result.attempts] == ["invalid_response", "ok"]
    assert result.model == "m2"


async def test_all_models_out_of_quota_raises_rate_limited() -> None:
    client = FakeGenaiClient([rate_limited(per_day=True)] * 3)

    with pytest.raises(LLMRateLimitedError) as exc:
        await generate(provider(client, FakeSleep()))

    assert [a.model for a in exc.value.attempts] == ["m1", "m2", "m3"]


async def test_all_models_failing_raises_unavailable() -> None:
    client = FakeGenaiClient([server_error(500)] * 6)

    with pytest.raises(LLMUnavailableError) as exc:
        await generate(provider(client, FakeSleep()))

    assert len(exc.value.attempts) == 6


async def test_bad_key_raises_at_once_without_fallback() -> None:
    client = FakeGenaiClient([bad_key()])

    with pytest.raises(LLMError) as exc:
        await generate(provider(client, FakeSleep()))

    assert not isinstance(exc.value, LLMUnavailableError | LLMRateLimitedError)
    assert client.models_called == ["m1"]


async def test_a_request_that_never_answers_times_out_and_falls_back() -> None:
    client, sleep = FakeGenaiClient([HANG, ok(PLAN_JSON)]), FakeSleep()
    p = GeminiProvider(
        "unused", MODELS, client=client, sleep=sleep, limiter=RateLimiter(sleep=sleep), timeout_s=0.05
    )

    result = await p.generate(system="s", prompt="p", schema=PlanOut)

    assert client.models_called == ["m1", "m2"]  # no retry of a stalled model
    assert result.attempts[0].status == "unavailable"
    assert result.attempts[0].message == "no answer within 0.05 s"
    assert result.model == "m2"


async def test_every_model_stalling_raises_unavailable() -> None:
    client, sleep = FakeGenaiClient([HANG, HANG, HANG]), FakeSleep()
    p = GeminiProvider(
        "unused", MODELS, client=client, sleep=sleep, limiter=RateLimiter(sleep=sleep), timeout_s=0.05
    )

    with pytest.raises(LLMUnavailableError):
        await p.generate(system="s", prompt="p", schema=PlanOut)


def test_empty_api_key_is_a_clear_error() -> None:
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiProvider("")


async def test_rate_limiter_waits_for_the_sixth_call_in_a_minute() -> None:
    now = [0.0]
    sleep = FakeSleep()
    limiter = RateLimiter(per_minute=5, sleep=sleep, clock=lambda: now[0])

    for _ in range(5):
        await limiter.wait("m1")
        now[0] += 1.0
    await limiter.wait("m1")
    await limiter.wait("m2")  # another model has its own budget

    assert sleep.slept == [55.0]


@pytest.mark.skipif(
    os.environ.get("KRAMA_LIVE_GEMINI") != "1", reason="live Gemini call; set KRAMA_LIVE_GEMINI=1"
)
async def test_live_gemini_returns_a_valid_plan() -> None:
    from app.config import get_settings
    from app.llm import DEFAULT_MODELS

    result = await GeminiProvider(get_settings().gemini_api_key, DEFAULT_MODELS).generate(
        system="Plan browser steps for Gitea. Targets use ARIA role + name. url_matches is a path regex.",
        prompt="Task: create a repository called demo-repo with a README. Signed in as demo, at /.",
        schema=PlanOut,
    )

    assert result.value.steps
    assert result.attempts[-1].status == "ok"


# --- a model that stalls or fails rests (#101) ---


def resting_provider(client: FakeGenaiClient, sleep: FakeSleep, now: list[float]) -> GeminiProvider:
    return GeminiProvider(
        "unused", MODELS, client=client, sleep=sleep, limiter=RateLimiter(sleep=sleep, clock=lambda: now[0]),
        timeout_s=0.05, cooldown_s=300, quota_cooldown_s=3600, clock=lambda: now[0],
    )  # fmt: skip


async def test_a_stalled_model_goes_last_until_it_has_rested() -> None:
    now = [1000.0]
    client = FakeGenaiClient([HANG, ok(PLAN_JSON), ok(PLAN_JSON), ok(PLAN_JSON)])
    p = resting_provider(client, FakeSleep(), now)

    await generate(p)  # m1 stalls, m2 answers
    await generate(p)  # m1 rests: m2 first, no second timeout
    now[0] += 301
    await generate(p)  # rested: m1 first again

    assert client.models_called == ["m1", "m2", "m2", "m1"]


async def test_a_model_failing_with_server_errors_rests_too() -> None:
    now = [0.0]
    client = FakeGenaiClient([server_error(503), ok(PLAN_JSON), ok(PLAN_JSON)])
    p = resting_provider(client, FakeSleep(), now)

    await generate(p)
    await generate(p)

    assert client.models_called == ["m1", "m2", "m2"]


async def test_a_model_out_of_daily_quota_rests_for_an_hour() -> None:
    now = [0.0]
    client = FakeGenaiClient([rate_limited(per_day=True), ok(PLAN_JSON), ok(PLAN_JSON), ok(PLAN_JSON)])
    p = resting_provider(client, FakeSleep(), now)

    await generate(p)
    now[0] += 1800
    await generate(p)  # still resting after 30 min
    now[0] += 1801
    await generate(p)  # an hour later it is tried first again

    assert client.models_called == ["m1", "m2", "m2", "m1"]


async def test_when_every_model_rests_they_are_still_tried_in_order() -> None:
    now = [0.0]
    client = FakeGenaiClient([HANG, HANG, HANG, ok(PLAN_JSON)])
    p = resting_provider(client, FakeSleep(), now)

    with pytest.raises(LLMUnavailableError):
        await generate(p)
    await generate(p)  # all resting: still tried, in the configured order

    assert client.models_called == ["m1", "m2", "m3", "m1"]
