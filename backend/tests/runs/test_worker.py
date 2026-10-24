"""The arq run worker (#95), for real: Redis, an arq worker in this process, the test Postgres, real Chromium
on the local test site. The API side is `ArqExecutor`; nothing is faked except the plan (already approved)."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from arq import create_pool
from arq.worker import Worker
from redis.asyncio import Redis

from app.config import Settings
from app.runs import RunStore
from app.runs.events import EventHub, RedisEventRelay
from app.runs.queue import JOB, ArqExecutor, job_id, redis_settings
from app.worker import worker_settings
from tests.runs.test_executor import Sessions, environment, events, queued_run, run_row
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = pytest.mark.anyio

REDIS_URL = "redis://127.0.0.1:6379/7"  # its own Redis database, emptied before each test
# A plan whose 2nd step is high risk: the run pauses there for a human (#59).
RISKY = [GOOD_PLAN["steps"][0], {**GOOD_PLAN["steps"][1], "risk": "high"}, *GOOD_PLAN["steps"][2:]]
SLOW = [
    *GOOD_PLAN["steps"][:1],
    step(2, {"type": "wait"}, {"role": "button", "name": "Never appears"}, "Wait.", {"url_matches": "/"}),
]


async def redis_up() -> bool:
    try:
        async with Redis.from_url(REDIS_URL, socket_connect_timeout=1) as r:
            return bool(await r.ping())
    except Exception:
        return False


@pytest.fixture
async def queue(sessions: Sessions, tmp_path: Path) -> AsyncIterator[dict[str, Any]]:
    if not await redis_up():
        pytest.skip(f"Redis isn't reachable at {REDIS_URL} (`just up`)")
    async with Redis.from_url(REDIS_URL) as r:
        await r.flushdb()
    settings = Settings(redis_url=REDIS_URL, max_concurrent_runs=1, run_timeout_seconds=120)
    hub = EventHub()
    relay = RedisEventRelay(REDIS_URL, hub)
    await relay.start()
    api_store = RunStore(sessions)  # the API side writes cancels and answers itself, as in the real API
    executor = ArqExecutor(api_store, REDIS_URL, artifacts_dir=tmp_path)
    started: list[Worker] = []
    tasks: list[asyncio.Task[None]] = []

    async def start_worker() -> Worker:
        kwargs = worker_settings(settings, sessions=sessions, environment=lambda: environment(tmp_path))
        worker = Worker(**{**kwargs, "poll_delay": 0.1})
        started.append(worker)
        tasks.append(asyncio.create_task(worker.async_run()))
        return worker

    yield {"executor": executor, "hub": hub, "start_worker": start_worker, "settings": settings}

    for worker in started:  # the Windows-safe stop (docs/research/phase-3-vishwas-job-queue.md)
        for task in list(worker.tasks.values()):
            task.cancel()
        if worker.main_task is not None:
            worker.main_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker.main_task
        await worker.close()
    await executor.shutdown()
    await relay.stop()


async def until(sessions: Sessions, run_id: UUID, *statuses: str, timeout_s: float = 60) -> str:
    for _ in range(int(timeout_s / 0.1)):
        status = (await run_row(sessions, run_id)).status
        if status in statuses:
            return status
        await asyncio.sleep(0.1)
    raise AssertionError(f"run never reached {statuses}: {(await run_row(sessions, run_id)).status}")


async def test_a_queued_run_executes_in_the_worker_and_its_events_reach_the_api(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    await queue["start_worker"]()
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    seen = queue["hub"].version(run_id)

    await queue["executor"].submit(run_id)
    await queue["executor"].wait(run_id, timeout_s=90)

    assert (await run_row(sessions, run_id)).status == "verified"
    types = [e["type"] for e in await events(sessions, run_id)]
    assert types[0] == "run.started" and types[-1] == "run.completed"
    assert queue["hub"].version(run_id) > seen  # the worker's events woke the API's live view


async def test_a_run_submitted_twice_is_queued_once(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"][:1])
    await queue["executor"].submit(run_id)
    await queue["executor"].submit(run_id)
    async with Redis.from_url(REDIS_URL) as r:
        assert await r.zcard("arq:queue") == 1

    await queue["start_worker"]()
    await queue["executor"].wait(run_id, timeout_s=60)
    starts = [e for e in await events(sessions, run_id) if e["type"] == "run.started"]
    assert len(starts) == 1


async def test_cancel_stops_a_run_the_worker_is_running(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    await queue["start_worker"]()
    run_id = await queued_run(sessions, site, SLOW)
    await queue["executor"].submit(run_id)
    await until(sessions, run_id, "running")

    assert await queue["executor"].cancel(run_id)

    await asyncio.sleep(1.5)
    run = await run_row(sessions, run_id)
    assert run.status == "cancelled"
    assert [e["type"] for e in await events(sessions, run_id)][-1] == "run.cancelled"


async def test_a_pause_answered_allow_through_the_api_resumes_in_the_worker(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    await queue["start_worker"]()
    run_id = await queued_run(sessions, site, RISKY)
    await queue["executor"].submit(run_id)
    await until(sessions, run_id, "paused")

    assert not await queue["executor"].confirm(run_id, 99, "allow")  # not paused at that step
    assert await queue["executor"].confirm(run_id, 2, "allow")

    await queue["executor"].wait(run_id, timeout_s=60)
    assert (await run_row(sessions, run_id)).status == "verified"
    assert "run.resumed" in [e["type"] for e in await events(sessions, run_id)]


async def test_a_pause_answered_deny_cancels_the_run(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    await queue["start_worker"]()
    run_id = await queued_run(sessions, site, RISKY)
    await queue["executor"].submit(run_id)
    await until(sessions, run_id, "paused")

    assert await queue["executor"].confirm(run_id, 2, "deny")

    await asyncio.sleep(1)
    assert (await run_row(sessions, run_id)).status == "cancelled"
    cancelled = [e for e in await events(sessions, run_id) if e["type"] == "run.cancelled"]
    assert cancelled and cancelled[0]["reason"] == "confirmation_denied"


async def test_a_job_whose_run_already_started_fails_as_interrupted(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    # arq re-runs a job a stopped worker didn't finish; on a real site the run must not run twice.
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"], status="running")
    pool = await create_pool(redis_settings(REDIS_URL))
    await pool.enqueue_job(JOB, str(run_id), _job_id=f"retry-{run_id}")  # as if left over from a dead worker
    await pool.aclose()

    await queue["start_worker"]()

    assert await until(sessions, run_id, "failed") == "failed"
    run = await run_row(sessions, run_id)
    assert run.error is not None and run.error["details"]["reason"] == "interrupted"


async def test_a_queued_run_redis_lost_is_picked_up_when_the_worker_starts(
    sessions: Sessions, site: str, queue: dict[str, Any]
) -> None:
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"][:1])  # in the database, never enqueued

    await queue["start_worker"]()

    assert await until(sessions, run_id, "verified", "failed") == "verified"
    async with Redis.from_url(REDIS_URL) as r:
        assert not await r.exists(f"arq:job:{job_id(run_id)}")  # done: nothing left queued


def test_the_job_id_is_one_per_run() -> None:
    run_id = UUID("6f1c2a4e-1111-4b8a-9a1b-123456789abc")
    assert job_id(run_id) == job_id(UUID(str(run_id))) == f"run:{run_id}"
