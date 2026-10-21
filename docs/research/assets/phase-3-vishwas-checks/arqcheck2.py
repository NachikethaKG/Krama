"""Phase 3 research check 2: abort, duplicate job ids, cross-process pause/confirm + pub/sub, graceful close."""

import asyncio
import time

from arq import create_pool, func
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus
from arq.worker import Worker
from redis.asyncio import Redis

REDIS = RedisSettings(host="127.0.0.1", port=6379, database=6)
T0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - T0:6.2f}s] {msg}", flush=True)


async def long_run(ctx, name: str):
    log(f"{name} running")
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        log(f"{name} got CancelledError (cleanup would close the page here)")
        raise


async def paused_run(ctx, run_id: str):
    """A run that pauses for a human: publish an event, wait for a confirm on a Redis list."""
    r: Redis = ctx["redis"]
    await r.publish(f"run:{run_id}", "paused at step 2")
    log("worker: paused, waiting for confirm")
    _, answer = await r.blpop(f"confirm:{run_id}", timeout=30)
    log(f"worker: got confirm {answer!r}")
    await r.publish(f"run:{run_id}", f"resumed: {answer.decode()}")
    return answer.decode()


async def shutdown(ctx):
    log("on_shutdown ran")


async def main():
    pool = await create_pool(REDIS)
    await pool.flushdb()
    worker = Worker(
        functions=[func(long_run, timeout=120), func(paused_run, timeout=120)],
        redis_settings=REDIS,
        max_jobs=1,
        allow_abort_jobs=True,
        poll_delay=0.2,
        on_shutdown=shutdown,
    )
    wtask = asyncio.create_task(worker.async_run())

    # 1. duplicate _job_id
    j1 = await pool.enqueue_job("long_run", "R1", _job_id="run-1")
    dup = await pool.enqueue_job("long_run", "R1-again", _job_id="run-1")
    log(f"duplicate _job_id -> {dup}")

    # 2. abort a running job
    await asyncio.sleep(1.5)
    log(f"status before abort: {await j1.status()}")
    log(f"abort -> {await j1.abort(timeout=10)}")
    info = await j1.result_info()
    log(f"after abort: success={info.success} result={type(info.result).__name__}")

    # 3. abort a queued job (worker busy with run-2)
    j2 = await pool.enqueue_job("long_run", "R2", _job_id="run-2")
    j3 = await pool.enqueue_job("long_run", "R3", _job_id="run-3")
    await asyncio.sleep(1)
    log(f"run-3 status while run-2 runs: {await j3.status()}")
    try:
        await j3.abort(timeout=0.5)
    except TimeoutError:
        log("abort queued run-3: flag set, result not ready while the slot is busy")
    log(f"abort running run-2 -> {await j2.abort(timeout=10)}")
    await asyncio.sleep(1)
    i3 = await j3.result_info()
    log(f"run-3 after slot freed: status={await j3.status()} success={getattr(i3, 'success', None)} result={type(getattr(i3, 'result', None)).__name__}")

    # 4. pause / confirm across processes-style boundary (API side uses its own Redis client)
    api = Redis(host="127.0.0.1", port=6379, db=6)
    async with api.pubsub() as ps:
        await ps.subscribe("run:abc")
        jp = await pool.enqueue_job("paused_run", "abc", _job_id="run-abc")
        msg = None
        while msg is None:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=5)
        log(f"api: SSE would send {msg['data']!r}")
        await api.rpush("confirm:abc", "allow")
        msg = None
        while msg is None:
            msg = await ps.get_message(ignore_subscribe_messages=True, timeout=5)
        log(f"api: SSE would send {msg['data']!r}")
    log(f"paused_run result: {await jp.result(timeout=10)!r}")

    # 5. graceful close on Windows (no signal handlers)
    await pool.enqueue_job("long_run", "R-at-shutdown", _job_id="run-last")
    await asyncio.sleep(1)
    for t in list(worker.tasks.values()):
        t.cancel()
    worker.main_task.cancel()
    try:
        await wtask
    except asyncio.CancelledError:
        pass
    await worker.close()
    log(f"run-last status after stop: {await Job('run-last', pool).status()}")
    log(f"worker closed; jobs complete={worker.jobs_complete} failed={worker.jobs_failed}")
    await api.aclose()
    await pool.aclose()


if __name__ == "__main__":
    asyncio.run(main())
