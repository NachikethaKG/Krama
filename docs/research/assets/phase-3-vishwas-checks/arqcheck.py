"""Phase 3 research check: does arq run on Windows with Playwright in the worker?"""

import asyncio
import sys
import time

from arq import Retry, cron, create_pool
from arq.connections import RedisSettings
from arq.jobs import Job

REDIS = RedisSettings(host="127.0.0.1", port=6379, database=5)
T0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - T0:6.2f}s] {msg}", flush=True)


async def startup(ctx):
    from playwright.async_api import async_playwright

    ctx["pw"] = await async_playwright().start()
    ctx["browser"] = await ctx["pw"].chromium.launch()
    log(f"startup: loop={type(asyncio.get_running_loop()).__name__} chromium={ctx['browser'].version}")


async def shutdown(ctx):
    await ctx["browser"].close()
    await ctx["pw"].stop()
    log("shutdown: browser closed")


async def browse(ctx, name: str, secs: float):
    log(f"{name} start (try {ctx['job_try']})")
    page = await ctx["browser"].new_page()
    await page.set_content(f"<h1>{name}</h1>")
    title = await page.inner_text("h1")
    await asyncio.sleep(secs)
    await page.close()
    log(f"{name} end")
    return title


async def flaky(ctx):
    log(f"flaky try {ctx['job_try']}")
    if ctx["job_try"] < 3:
        raise Retry(defer=0.5)
    return "ok after retries"


async def tick(ctx):
    log("cron tick")


class WorkerSettings:
    functions = [browse, flaky]
    cron_jobs = [cron(tick, second={0, 15, 30, 45}, run_at_startup=False)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = REDIS
    max_jobs = 1
    job_timeout = 3
    max_tries = 5
    allow_abort_jobs = True
    poll_delay = 0.2


async def enqueue():
    redis = await create_pool(REDIS)
    await redis.flushdb()
    a = await redis.enqueue_job("browse", "A", 1.0)
    b = await redis.enqueue_job("browse", "B", 1.0)
    slow = await redis.enqueue_job("browse", "SLOW", 10.0)
    fl = await redis.enqueue_job("flaky")
    ab = await redis.enqueue_job("browse", "ABORTME", 20.0, _job_id="abort-me")
    dup = await redis.enqueue_job("browse", "DUP", 0.1, _job_id="abort-me")
    log(f"duplicate _job_id enqueue returned: {dup}")
    for name, job in [("A", a), ("B", b), ("SLOW", slow), ("flaky", fl)]:
        try:
            log(f"result {name}: {await job.result(timeout=40)!r}")
        except Exception as e:  # noqa: BLE001
            log(f"result {name}: {type(e).__name__}: {e}")
    await asyncio.sleep(0.5)
    log(f"abort -> {await Job('abort-me', redis).abort(timeout=10)}")
    info = await Job("abort-me", redis).result_info()
    log(f"abort-me result_info success={getattr(info, 'success', None)} result={getattr(info, 'result', None)!r}")


if __name__ == "__main__":
    asyncio.run(enqueue())
