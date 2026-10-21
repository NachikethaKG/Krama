# Job queue: arq on Windows, cron, retries, timeouts, one browser at a time

- **Phase:** 3
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-21; decisions by Vishwas)
- **Question(s):** **Job queue:** does **arq** run on Windows? Cron jobs, retries, timeouts, and limiting to one
  browser at a time.

Checks: [`assets/phase-3-vishwas-checks/arqcheck.py`](assets/phase-3-vishwas-checks/arqcheck.py) (worker through
the `arq` CLI) and [`arqcheck2.py`](assets/phase-3-vishwas-checks/arqcheck2.py) (worker in code), output in
[`output.txt`](assets/phase-3-vishwas-checks/output.txt). Setup: Windows 11, Python 3.12, arq 0.28.0, Redis 7.4.11 in
Docker Desktop, Playwright 1.64.

## Findings

**Status**
- arq 0.28.0, released 2026-04-16, supports Python 3.9–3.14. [verified: https://pypi.org/project/arq/]
- README: "**In maintenance only mode**: arq is in maintenance only mode, see #510." Issue #510 (2025-10-18, Samuel
  Colvin): "the pydantic team and I don't have time right now to put significant effort into arq", "we won't archive
  this repo", critical security fixes only. [verified: https://github.com/python-arq/arq/issues/510]

**Yes, it runs on Windows** [verified locally]
- The `arq` CLI worker starts. `on_startup` launches Chromium in the worker's `ProactorEventLoop` (the loop Playwright
  needs on Windows), and every job reuses that browser.
- `max_jobs=1`: queued jobs ran strictly one after another, in order.
- **Timeout:** `job_timeout` (or `func(..., timeout=)` per function) cancels the job with `asyncio.wait_for`. The job
  ends as failed with `TimeoutError` and is not retried.
- **Retries:** `raise Retry(defer=0.5)` re-ran a job; it succeeded on try 3 (`max_tries` counts tries).
- **Cron:** `cron(tick, second={0, 15, 30, 45})` fired on schedule.
- **Abort** (`allow_abort_jobs=True`): `Job.abort()` on a running job raises `CancelledError` inside it, so cleanup in
  `except/finally` runs. The result is `success=False`.
  - Aborting a **queued** job works too, but `abort()` waits for the result, which only comes once the busy slot frees
    up. Call it with a short timeout and don't wait for it.
- **Duplicate `_job_id`:** `enqueue_job` returns `None`, so a run can't be queued twice.

**Windows-specific problems we hit** [verified locally]
1. **`localhost` is slow to reach Redis from Python.** Docker Desktop publishes `[::]:6379`, but connecting to `::1`
   times out. Sync redis-py falls back to IPv4. arq's async connect (1 s timeout, 5 retries) failed every time. Use
   `127.0.0.1`, not `localhost`, in `REDIS_URL`.
2. **No graceful SIGTERM on Windows:** arq skips signal handlers when `loop.add_signal_handler` raises
   `NotImplementedError`. [verified: https://github.com/python-arq/arq/blob/main/arq/worker.py]
   - Worse, `Worker(handle_signals=False).close()` crashes on Windows with
     `AttributeError: module 'signal' has no attribute 'SIGUSR1'`.
   - What works: keep the default `handle_signals=True`, cancel `worker.tasks` and `worker.main_task`, then
     `await worker.close()` (runs `on_shutdown`).
   - Ctrl+C on the CLI ends via `KeyboardInterrupt` → `close()`.
3. **Pessimistic execution:** a job that is running when the worker stops **stays queued and runs again** on the next
   start. "Jobs aren't removed from the queue until they've either succeeded or failed."
   [verified: https://arq-docs.helpmanual.io/ and locally: `run-last` was `queued` after the stop]. For a browser run
   that half-created a repo, running again blindly is wrong.

**Pausing for a human inside a job** [verified locally]
- A job that pauses can wait on a Redis list (`BLPOP confirm:<run>`) while the API pushes the answer (`RPUSH`). Live
  events go worker → API over Redis pub/sub (`PUBLISH run:<id>`, the SSE handler `SUBSCRIBE`s). Both worked across
  two separate clients.
- Pub/sub keeps nothing, so a late SSE subscriber must first read `run_events` from Postgres (as now), then follow live
  messages. That is the design the current `EventHub` already has.
- A paused job holds the worker slot (and the browser) while it waits. With `MAX_CONCURRENT_RUNS=1` that's the same
  as today. The job timeout must cover running time + pause time (600 s + 1800 s today), or the job enforces
  `run_timeout_s` itself, which `InProcessExecutor` already does.

**One browser at a time**
- `max_jobs` limits one worker process; arq has nothing across processes.
  [verified: https://github.com/python-arq/arq/blob/main/arq/worker.py, by absence]
- One worker process with `max_jobs=MAX_CONCURRENT_RUNS` is enough for us. Several workers would need a Redis lock.

**Alternatives**

| | Windows | asyncio | cron | abort | maintained |
|---|---|---|---|---|---|
| **arq 0.28** | yes (above) | yes | yes | yes | security fixes only |
| taskiq 0.13 + taskiq-redis | "OS Independent" [verified: PyPI] | yes | via scheduler | [unverified] | active (Sep 2026) |
| SAQ 0.26 | not listed (Linux/Mac/Unix) [verified: PyPI] | yes | yes | yes | active |
| Dramatiq 2.2 | likely [unverified] | threads | no (APScheduler) | add-on | active |
| Celery | **no** since 4.x [verified: https://docs.celeryq.dev/en/stable/faq.html] | no | beat | revoke | active |
| RQ | **no**, needs `fork()` [verified: https://python-rq.org/docs/] | no | add-on | yes | active |
| Procrastinate (Postgres only) | [unverified] | yes | yes | yes | active |

## Recommendation

**Keep arq** (already fixed in `architecture.md` §Jobs). It works on Windows today, is small enough to read, and its
maintenance-only status doesn't bite in this project's lifetime. If it ever must go, taskiq is the closest async
replacement. The `RunExecutor` port keeps that swap local. **No ADR.** Design for #95:
1. **`ArqExecutor` behind `RunExecutor`.**
   - `submit` enqueues `run_job(run_id)` with `_job_id=str(run_id)`.
   - `cancel` sets the run cancelled in the DB, then calls `Job.abort(timeout=0.1)` without waiting.
   - `confirm` pushes the answer to `confirm:<run_id>`.
2. **Worker process** (`krama worker`):
   - `max_jobs = MAX_CONCURRENT_RUNS`, `allow_abort_jobs=True`, `max_tries=1` (a browser run is never retried
     automatically; the user starts a new run).
   - `job_timeout` = run timeout + pause timeout + margin; the job enforces `run_timeout_s` itself.
   - One Chromium per worker, launched in `on_startup`, with a fresh context per run.
3. **Idempotent start:** the job first reads the run's status. Anything but `queued` (a re-picked job after a crash) →
   mark it `failed` ("interrupted") and return. That is the existing `recover()` rule, moved into the job.
4. **Events:** the worker's `RunStore` commits as now, then `PUBLISH run:<id>`. The API's `EventHub` becomes a Redis
   subscriber with the same `version` / `wait` contract, so SSE code barely changes.
5. **Windows:**
   - `REDIS_URL=redis://127.0.0.1:6379/0` in `.env.example`.
   - Stop the worker by cancelling tasks then `close()`, never `handle_signals=False`.
   - The API keeps working with the in-process executor when `KRAMA_EXECUTOR=inprocess`, so tests and a no-Redis dev
     setup still work.
6. **Cron:** not needed in Phase 3; Phase 4's scheduled re-validation uses `cron(..., unique=True)`.

## Open questions
- `.env.example` is shared: changing `REDIS_URL` to `127.0.0.1` goes in its own small PR (with #95).
- Does Nachiketha's laptop show the same IPv6 `localhost` problem? (Same Docker Desktop, likely yes.)
- The SSE subscriber per open live view: fine for a demo; one shared subscription per API process would scale better.

## Links
- https://github.com/python-arq/arq, https://github.com/python-arq/arq/issues/510
- https://arq-docs.helpmanual.io/
- https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
- https://docs.celeryq.dev/en/stable/faq.html, https://python-rq.org/docs/
