"""Per-site limits for scheduled validation (docs/research/phase-4-nachiketha-scheduling-and-rate-limits.md):
a gap between validations on one site, a daily cap on GitHub, and a breaker that stops validating a site for
24 h after 3 `blocked` results in a row. Kept in Redis, so a worker restart doesn't forget them."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError


@dataclass(frozen=True)
class SiteRules:
    gap_s: float
    per_day: int | None


GITHUB = SiteRules(gap_s=60, per_day=10)
OTHER = SiteRules(gap_s=2, per_day=None)
BREAKER_STRIKES = 3
BREAKER_S = 24 * 3600


def rules_for(site: str) -> SiteRules:
    return GITHUB if site.lower().split(":")[0] in ("github.com", "www.github.com") else OTHER


class SiteLimits(Protocol):
    async def allowed(self, site: str) -> bool:
        """Whether a validation on `site` may start now (gap, daily cap, breaker)."""
        ...

    async def started(self, site: str) -> None:
        """A validation on `site` started: counts toward the gap and the daily cap."""
        ...

    async def finished(self, site: str, *, blocked: bool) -> None:
        """A blocked result is a strike against the site; anything else clears the strikes."""
        ...


class RedisSiteLimits:
    """`SiteLimits` in Redis. Fails closed: if Redis can't be reached, nothing is validated."""

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url

    async def allowed(self, site: str) -> bool:
        rules = rules_for(site)
        try:
            async with Redis.from_url(self._url, socket_connect_timeout=2) as r:
                if await r.exists(_key("breaker", site)):
                    return False
                last = await r.get(_key("last", site))
                if last is not None and _now() - float(last) < rules.gap_s:
                    return False
                if rules.per_day is not None:
                    used = await r.get(_key("count", site, _day()))
                    if used is not None and int(used) >= rules.per_day:
                        return False
                return True
        except (RedisError, OSError, ValueError):
            return False

    async def started(self, site: str) -> None:
        try:
            async with Redis.from_url(self._url, socket_connect_timeout=2) as r:
                await r.set(_key("last", site), str(_now()), ex=24 * 3600)
                count = _key("count", site, _day())
                await r.incr(count)
                await r.expire(count, 2 * 24 * 3600)
        except (RedisError, OSError):
            pass

    async def finished(self, site: str, *, blocked: bool) -> None:
        try:
            async with Redis.from_url(self._url, socket_connect_timeout=2) as r:
                strikes = _key("strikes", site)
                if not blocked:
                    await r.delete(strikes)
                    return
                if int(await r.incr(strikes)) >= BREAKER_STRIKES:
                    await r.set(_key("breaker", site), "1", ex=BREAKER_S)
                    await r.delete(strikes)
        except (RedisError, OSError):
            pass


def _key(kind: str, site: str, *rest: str) -> str:
    return ":".join(["krama:validation", kind, site.lower(), *rest])


def _now() -> float:
    return datetime.now(UTC).timestamp()


def _day() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")
