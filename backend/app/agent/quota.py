"""Daily quota tracking for Gemini self-healing requests (Phase 4 decision D12).

Enforces a strict cap of at most 5 Gemini heal calls per UTC day, tracked in Redis.
Key: krama:ratelimit:gemini_heal:<YYYY-MM-DD>
When the quota is exhausted and deterministic healing fails: abort self-healing,
mark the workflow as outdated, and flag the step with "retry AI fix".
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

DAILY_GEMINI_HEAL_LIMIT = 5
REDIS_KEY_PREFIX = "krama:ratelimit:gemini_heal"


def quota_key(date_str: str | None = None) -> str:
    """Computes the Redis quota key for a specific UTC date (default: today)."""
    if date_str is None:
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    return f"{REDIS_KEY_PREFIX}:{date_str}"


async def check_and_consume_gemini_heal_quota(redis: Redis | None) -> bool:
    """Atomically checks and consumes one Gemini heal call if quota is available.

    Returns True if quota was consumed (call is allowed, count <= 5).
    Returns False if quota is exhausted (count > 5).
    If Redis is None, denies access as a safeguard against untracked API calls.
    """
    if redis is None:
        return False

    key = quota_key()
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, 86400 * 2)  # 48h TTL
    return bool(current <= DAILY_GEMINI_HEAL_LIMIT)


async def get_gemini_heal_quota_status(redis: Redis | None) -> tuple[int, int]:
    """Returns (used_count, daily_limit)."""
    if redis is None:
        return (DAILY_GEMINI_HEAL_LIMIT, DAILY_GEMINI_HEAL_LIMIT)

    key = quota_key()
    val = await redis.get(key)
    used = int(val) if val is not None else 0
    return (used, DAILY_GEMINI_HEAL_LIMIT)


async def reset_gemini_heal_quota(redis: Redis | None, date_str: str | None = None) -> None:
    """Resets the quota counter for testing or administrative override."""
    if redis is not None:
        key = quota_key(date_str)
        await redis.delete(key)
