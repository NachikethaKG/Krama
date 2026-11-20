"""Runs in a worker process (#95): Redis + arq, one browser at a time.

Design: docs/research/phase-3-vishwas-job-queue.md. The API process enqueues a run (`ArqExecutor`); the
worker (`app/worker.py`, `just backend worker`) runs it with the same `InProcessExecutor` as before. The
database stays the source of truth: the API records a cancel or an answer to a pause there first, then tells
the worker over a Redis channel, and the worker publishes every committed event so the API's live-view
streams wake up (`RedisEventRelay`).

Two arq behaviours shape this: a job interrupted by a worker stop stays queued and runs again, so a run that
is already past `queued` when its job starts is failed as interrupted, never replayed; and `_job_id` keeps a
run from being queued twice.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Literal
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.runs.states import RunStatus
from app.runs.store import RunNotFoundError, RunStore
from app.runs.takeover import FrameSink, Notice
from app.runs.takeover_relay import ApiTakeoverRelay, RemoteTakeover

JOB = "run_job"
CONTROL = "krama:runs:control"
"""API → worker: {"action": "stop" | "resume", "run_id": ...}."""
FINAL = frozenset({RunStatus.VERIFIED, RunStatus.FAILED, RunStatus.CANCELLED})

type Decision = Literal["allow", "deny"]


def redis_settings(url: str) -> RedisSettings:
    return RedisSettings.from_dsn(url)


def job_id(run_id: UUID) -> str:
    return f"run:{run_id}"


class ArqExecutor:
    """The `RunExecutor` port in the API process when runs execute in the worker."""

    def __init__(self, store: RunStore, redis_url: str, *, artifacts_dir: Path) -> None:
        self._store = store
        self._url = redis_url
        self._pool: ArqRedis | None = None
        self.artifacts_dir = artifacts_dir
        self._takeovers = ApiTakeoverRelay(self._redis)

    async def _redis(self) -> ArqRedis:
        if self._pool is None:
            self._pool = await create_pool(redis_settings(self._url))
        return self._pool

    async def submit(self, run_id: UUID) -> None:
        await (await self._redis()).enqueue_job(JOB, str(run_id), _job_id=job_id(run_id))

    async def cancel(self, run_id: UUID) -> bool:
        if not await self._store.cancel(run_id, reason="user"):
            return False
        await self._signal("stop", run_id)  # a queued run just never starts: its job sees "cancelled"
        return True

    async def confirm(self, run_id: UUID, step_seq: int, decision: Decision) -> bool:
        try:
            status, current = await self._store.current_step(run_id)
        except RunNotFoundError:
            return False
        if status is not RunStatus.PAUSED or current != step_seq:
            return False
        if decision == "deny":
            if not await self._store.cancel(run_id, reason="confirmation_denied"):
                return False
            await self._signal("stop", run_id)
            return True
        resumed = {"step_seq": step_seq, "decision": "allow"}
        if not await self._store.transition(run_id, RunStatus.RUNNING, resumed, from_=RunStatus.PAUSED):
            return False  # e.g. the pause timed out in the worker meanwhile
        await self._signal("resume", run_id)
        return True

    def takeover(self, run_id: UUID) -> RemoteTakeover | None:
        """The run's active takeover, relayed from the worker (ADR 0008, #413)."""
        return self._takeovers.takeover(run_id)

    async def start_takeover(
        self,
        run_id: UUID,
        on_frame: FrameSink,
        *,
        on_blocked: Notice | None = None,
        on_end: Notice | None = None,
    ) -> RemoteTakeover:
        return await self._takeovers.start(run_id, on_frame, on_blocked, on_end)

    async def hand_back(self, run_id: UUID, step_seq: int, done: str) -> bool:
        return await self._takeovers.hand_back(run_id, step_seq, done)

    async def recover(self) -> list[UUID]:
        """Nothing here: the worker owns the browsers, so it recovers its own runs when it starts."""
        return []

    async def wait(self, run_id: UUID, timeout_s: float = 600.0) -> None:
        """Wait until the run is finished (tests). Polls the database."""
        deadline = time.monotonic() + timeout_s
        while await self._store.status(run_id) not in FINAL:
            if time.monotonic() > deadline:
                raise TimeoutError(f"run {run_id} not finished after {timeout_s:g} s")
            await asyncio.sleep(0.2)

    async def shutdown(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None

    async def _signal(self, action: str, run_id: UUID) -> None:
        await (await self._redis()).publish(CONTROL, json.dumps({"action": action, "run_id": str(run_id)}))
