"""Wakes live-view streams when a run gets a new event (docs/research/phase-1-vishwas-sse.md).

The database stays the source of truth: a woken stream re-reads `run_events`. A per-run version counter means
an event committed between a stream's query and its wait is never missed, and the wait has a timeout as a
safety net anyway. In-process only (Phases 0-2); Phase 3 moves runs to a worker and this to Redis or
Postgres LISTEN/NOTIFY.
"""

import asyncio
import contextlib
from collections import defaultdict
from uuid import UUID


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
