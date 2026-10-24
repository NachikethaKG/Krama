"""Wakes live-view streams when a run gets a new event (docs/research/phase-1-vishwas-sse.md).

The database stays the source of truth: a woken stream re-reads `run_events`. A per-run version counter means
an event committed between a stream's query and its wait is never missed, and the wait has a timeout as a
safety net anyway. With the arq worker (#95) the events are committed in another process; `RedisEventRelay`
carries the wake-ups over Redis.
"""

import asyncio
import contextlib
import logging
from collections import defaultdict
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

EVENTS = "krama:runs:events"
"""Redis channel, worker → API: a run id whenever one of its events was committed (#95)."""


class EventHub:
    def __init__(self) -> None:
        self._versions: defaultdict[UUID, int] = defaultdict(int)
        self._changed = asyncio.Condition()

    def version(self, run_id: UUID) -> int:
        """Read this BEFORE querying the database, then pass it to `wait`."""
        return self._versions[run_id]

    async def notify(self, run_id: UUID) -> None:
        """Call after an event for `run_id` was committed."""
        async with self._changed:
            self._versions[run_id] += 1
            self._changed.notify_all()

    async def wait(self, run_id: UUID, seen: int, max_wait_s: float = 5.0) -> None:
        """Return once `run_id` has events newer than version `seen`, or after `max_wait_s` seconds."""
        with contextlib.suppress(TimeoutError):
            async with asyncio.timeout(max_wait_s), self._changed:
                await self._changed.wait_for(lambda: self._versions[run_id] > seen)


class RedisEventRelay:
    """With the arq worker (#95): the worker publishes a run id on `EVENTS` after each committed event; this
    wakes the matching streams of the in-process `EventHub`. A missed message costs nothing but latency: a
    stream re-reads `run_events` on every wake-up and after its timeout anyway."""

    def __init__(self, redis_url: str, hub: EventHub) -> None:
        self._url = redis_url
        self._hub = hub
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._listen(), name="redis-event-relay")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._ready.wait(), 5)  # subscribed before the API takes requests

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _listen(self) -> None:
        while True:
            try:
                async with Redis.from_url(self._url) as redis, redis.pubsub() as pubsub:
                    await pubsub.subscribe(EVENTS)
                    self._ready.set()
                    async for message in pubsub.listen():
                        if message.get("type") == "message":
                            with contextlib.suppress(ValueError):
                                await self._hub.notify(UUID(message["data"].decode()))
            except asyncio.CancelledError:
                raise
            except Exception:  # Redis restarted or briefly unreachable: streams still poll, so retry calmly
                logger.warning("event relay lost Redis, retrying in 2 s", exc_info=True)
                await asyncio.sleep(2)
