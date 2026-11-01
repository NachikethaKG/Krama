"""Per-site limits in Redis (#110): the gap between validations, GitHub's daily cap, the 3-strike breaker.
Needs Redis (`just up`); each test uses its own made-up site names, and cleans its keys."""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.validation import RedisSiteLimits
from app.validation.limits import rules_for

pytestmark = pytest.mark.anyio
REDIS_URL = "redis://127.0.0.1:6379/7"


@pytest.fixture
async def limits() -> AsyncIterator[RedisSiteLimits]:
    try:
        async with Redis.from_url(REDIS_URL, socket_connect_timeout=1) as r:
            await r.ping()
    except Exception:
        pytest.skip(f"Redis isn't reachable at {REDIS_URL} (`just up`)")
    yield RedisSiteLimits(REDIS_URL)
    async with Redis.from_url(REDIS_URL) as r:
        for key in await r.keys("krama:validation:*test-*"):
            await r.delete(key)


def site() -> str:
    return f"test-{uuid4().hex[:8]}.example:3001"


def test_github_has_the_strict_rules() -> None:
    assert (rules_for("github.com").gap_s, rules_for("github.com").per_day) == (60, 10)
    assert (rules_for("127.0.0.1:3001").gap_s, rules_for("127.0.0.1:3001").per_day) == (2, None)


async def test_a_site_waits_its_gap_after_a_validation_started(limits: RedisSiteLimits) -> None:
    s = site()
    assert await limits.allowed(s)

    await limits.started(s)

    assert not await limits.allowed(s)  # 2 s gap for a non-GitHub site


async def test_three_blocked_in_a_row_trip_the_breaker_and_a_success_clears_strikes(
    limits: RedisSiteLimits,
) -> None:
    flaky, broken = site(), site()
    for blocked in (True, True, False, True, True):
        await limits.finished(flaky, blocked=blocked)
    for _ in range(3):
        await limits.finished(broken, blocked=True)

    async with Redis.from_url(REDIS_URL) as r:
        assert not await r.exists(f"krama:validation:breaker:{flaky}")  # the success in between reset it
        assert await r.ttl(f"krama:validation:breaker:{broken}") > 23 * 3600
    assert not await limits.allowed(broken)


async def test_without_redis_nothing_is_validated() -> None:
    assert not await RedisSiteLimits("redis://127.0.0.1:1/0").allowed(site())  # fails closed
