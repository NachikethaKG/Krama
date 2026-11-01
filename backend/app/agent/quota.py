"""The daily Gemini heal budget (D12 in docs/research/phase-4-decisions-alignment.md): at most 5 heal calls
per UTC day, counted in Redis so the API process and the worker share one count. Planning keeps its own
quota."""

from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

DAILY_HEAL_CALLS = 5
_KEY = "krama:gemini_heal:{day}"


def budget_key(now: datetime | None = None) -> str:
    return _KEY.format(day=(now or datetime.now(UTC)).strftime("%Y-%m-%d"))


class RedisHealBudget:
    """`HealBudget` on Redis. Fails closed: if Redis can't be reached, no Gemini heal."""

    def __init__(self, redis_url: str, limit: int = DAILY_HEAL_CALLS) -> None:
        self._url = redis_url
        self._limit = limit

    async def take(self) -> bool:
        try:
            async with Redis.from_url(self._url, socket_connect_timeout=2) as redis:
                key = budget_key()
                used = int(await redis.incr(key))
                if used == 1:
                    await redis.expire(key, 2 * 24 * 3600)  # gone a day after its day ends
                return used <= self._limit
        except (RedisError, OSError):
            return False
