"""The run worker (#95): `just backend worker` (= `uv run krama worker`). Needs Redis (`just up`) and
RUN_EXECUTOR=arq for the API, so the API enqueues runs instead of running them itself.

One worker process runs at most MAX_CONCURRENT_RUNS runs at once (1 locally: one browser at a time). Each
run is the same `InProcessExecutor` code as before; this module only adds the arq job, the control channel
(cancel, answers to pauses) and the event relay (docs/research/phase-3-vishwas-job-queue.md).
"""

import asyncio
import contextlib
import json
import logging
import logging.config
from collections.abc import Callable
from typing import Any
from uuid import UUID

from arq import func
from arq.connections import ArqRedis
from arq.cron import cron
from arq.logs import default_log_config
from arq.worker import Worker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.services import build_run_environment
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.runs import InProcessExecutor, RunEnvironment, RunStore
from app.runs.events import EVENTS
from app.runs.queue import CONTROL, JOB, job_id, redis_settings
from app.runs.states import RunStatus
from app.storage import LocalFsStore
from app.storage.cleanup import cleanup_with_settings

logger = logging.getLogger(__name__)

type Ctx = dict[str, Any]
STALE = (RunStatus.RUNNING, RunStatus.PAUSED)
"""Statuses a run can't be in when its job starts, unless a worker died under it."""
INTERRUPTED = "Interrupted by a worker restart"


async def run_job(ctx: Ctx, run_id: str) -> str:
    """One run, start to end. A run already past `queued` was interrupted (its job came back after a worker
    stop): it fails instead of running twice on a real site."""
    rid = UUID(run_id)
    store: RunStore = ctx["store"]
    executor: InProcessExecutor = ctx["executor"]
    status = await store.status(rid)
    if status in STALE:
        await store.fail(rid, from_=status, message=INTERRUPTED, reason="interrupted")
        return "interrupted"
    if status is not RunStatus.QUEUED:
        return status.value  # cancelled before it started
    await executor.submit(rid)
    try:
        await executor.wait(rid)
    except asyncio.CancelledError:  # arq's job timeout or a worker stop: close the browser, don't leak it
        await executor.stop(rid)
        raise
    return (await store.status(rid)).value


async def export_cleanup_job(ctx: Ctx) -> str:
    """Daily at 03:30 (#125): expire old exports, keep exports/ under EXPORTS_MAX_GB, drop unused clips."""
    report = await cleanup_with_settings(ctx["settings"], ctx["sessions"], ctx["files"])
    return report.summary()


async def _listen_for_control(redis_url: str, executor: InProcessExecutor) -> None:
    """Cancel and pause answers from the API, already recorded in the database there."""
    from redis.asyncio import Redis

    while True:
        try:
            async with Redis.from_url(redis_url) as redis, redis.pubsub() as pubsub:
                await pubsub.subscribe(CONTROL)
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        signal = json.loads(message["data"])
                        rid = UUID(signal["run_id"])
                    except (ValueError, KeyError, TypeError):
                        continue
                    if signal.get("action") == "stop":
                        await executor.stop(rid)
                    elif signal.get("action") == "resume":
                        executor.resume(rid)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("worker lost Redis for control messages, retrying in 2 s", exc_info=True)
            await asyncio.sleep(2)


async def _recover(store: RunStore, redis: ArqRedis) -> None:
    """Runs a dead worker left running or paused have no browser any more: they fail. Queued ones are enqueued
    again (deduplicated by job id), in case Redis lost them."""
    for rid in await store.unfinished():
        status = await store.status(rid)
        if status in STALE:
            await store.fail(rid, from_=status, message=INTERRUPTED, reason="interrupted")
        elif status is RunStatus.QUEUED:
            await redis.enqueue_job(JOB, str(rid), _job_id=job_id(rid))


def worker_settings(
    settings: Settings,
    *,
    sessions: async_sessionmaker[AsyncSession] | None = None,
    environment: Callable[[], RunEnvironment] | None = None,
) -> dict[str, Any]:
    """Keyword arguments for `arq.worker.Worker`. Tests pass their own database and run environment."""
    state: dict[str, Any] = {}

    async def startup(ctx: Ctx) -> None:
        engine = None
        own_sessions = sessions
        if own_sessions is None:
            engine = create_engine(settings.database_url)
            own_sessions = create_sessionmaker(engine)
        redis: ArqRedis = ctx["redis"]

        async def published(run_id: UUID) -> None:
            await redis.publish(EVENTS, str(run_id))

        store = RunStore(own_sessions, on_event=published)
        env = environment() if environment is not None else build_run_environment(settings)
        executor = InProcessExecutor(store, env, max_concurrent=settings.max_concurrent_runs)
        ctx.update(
            store=store,
            executor=executor,
            sessions=own_sessions,
            settings=settings,
            files=LocalFsStore(settings.artifacts_dir),
        )
        state["engine"] = engine
        state["listener"] = asyncio.create_task(_listen_for_control(settings.redis_url, executor))
        await _recover(store, redis)
        logger.info("worker ready: %d run(s) at a time", settings.max_concurrent_runs)

    async def shutdown(ctx: Ctx) -> None:
        listener = state.get("listener")
        if listener is not None:
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener
        if "executor" in ctx:
            await ctx["executor"].shutdown()
        if state.get("engine") is not None:
            await state["engine"].dispose()

    # A run may pause for a human (up to the pause timeout) besides running: arq's own timeout is only the
    # last safety net; the run enforces RUN_TIMEOUT_SECONDS itself.
    timeout = settings.run_timeout_seconds + 1800 + 120
    return {
        "functions": [func(run_job, name=JOB, timeout=timeout, max_tries=1)],
        # Local time. `unique`: with two workers, only one of them cleans up.
        "cron_jobs": [cron(export_cleanup_job, hour=3, minute=30, timeout=600, unique=True)],
        "redis_settings": redis_settings(settings.redis_url),
        "on_startup": startup,
        "on_shutdown": shutdown,
        "max_jobs": settings.max_concurrent_runs,
        "keep_result": 60,
        "poll_delay": 0.5,
        "handle_signals": True,  # Windows: arq skips the handlers; False would crash close() (no SIGUSR1)
    }


def run_worker(settings: Settings) -> None:
    """The `krama worker` command. Ctrl+C stops it; running runs then end as interrupted on the next start."""
    # arq's job log (one line per job), as its own CLI sets it up
    logging.config.dictConfig(default_log_config(verbose=False))
    worker = Worker(**worker_settings(settings))
    worker.run()
