"""Real-site benchmark (#481) for the Phase 7 exit gate (#482): Krama on public sites it wasn't built on.

Each task takes the product path, like `ApiAgentRunner`: sign in, POST /tasks, approve the outline, follow
the run.

- A pause to confirm a risky step is allowed (the owner would confirm it) and counted.
- Any other pause needs a human: with `--interactive` the live-view link is printed and the runner waits for
  the owner (one takeover), otherwise the task fails.
- A verified run passes when its final page matches the task's `success` (URL regex on path?query, title).
- Then the stored tutorial is replayed once, with no LLM: "Do it for me" with new values when the workflow
  has inputs (a create task must not collide with what it created), else a reverify.
- LLM calls and decision latency come from the `llm_calls` table (#464).

Run from the repo root (the API on :8000, `LLM_PROVIDER=gemini` for the gate):

    uv run --project backend python -m benchmarks.real_sites [--only NAME ...] [--account none|own|all]
        [--interactive] [--out benchmarks/results/real-sites] [--fresh] [--daily-calls 40] [--per-task 15]

Gemini's free tier allows 20 requests per model per day, about 3 tasks (#494). So the gate runs over several
days: each run resumes from `gate.json`, skips tasks that have a verdict, and stops before a task that today's
quota can't finish. A task the quota stopped halfway is marked `quota` and runs again on a later day.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml  # type: ignore[import-untyped]

from benchmarks.api_runner import FINAL, ApiAgentRunner

TASKS_FILE = Path(__file__).resolve().parent / "tasks" / "real-sites" / "gate.yaml"


@dataclass(frozen=True)
class SiteTask:
    name: str
    site: str
    target: str
    prompt: str
    account: str = "none"
    success: dict[str, str] = field(default_factory=dict)


@dataclass
class SiteResult:
    name: str
    site: str
    outcome: str = "not_run"
    """verified, wrong_page, failed, paused, needs_sign_in, planning_<status>, error; `quota` when it didn't
    pass and the LLM's daily quota ran out during it (#494): not a verdict on Krama, so it runs again."""
    why: str | None = None
    seconds: float = 0.0
    takeovers: int = 0
    confirmations: int = 0
    llm_calls: int = 0
    decision_ms: list[int] = field(default_factory=list)
    final_url: str | None = None
    workflow_id: str | None = None
    replay: str | None = None
    """verified / failed / skipped (not verified first)."""
    replay_llm_calls: int | None = None

    @property
    def passed(self) -> bool:
        return (
            self.outcome == "verified"
            and self.takeovers <= 1
            and self.replay == "verified"
            and not self.replay_llm_calls
        )


def load_tasks(path: Path = TASKS_FILE) -> list[SiteTask]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [SiteTask(**t) for t in data.get("tasks", [])]


def matches(success: dict[str, str], url: str | None, title: str | None) -> bool:
    """Does the final page satisfy the task's `success`? `url` is path?query (no host)."""
    if "url_matches" in success and not (url is not None and re.search(success["url_matches"], url)):
        return False
    return not (
        "title_contains" in success and success["title_contains"].lower() not in (title or "").lower()
    )


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


class RealSiteRunner:
    def __init__(self, api_url: str = "http://127.0.0.1:8000/api/v1", *, interactive: bool = False,
                 timeout: float = 900.0) -> None:  # fmt: skip
        self.api = ApiAgentRunner(target_url="", api_url=api_url, timeout=timeout, poll_s=2.0)
        self.web_url = api_url.split("/api/")[0].replace(":8000", ":3000")
        self.interactive = interactive
        self.timeout = timeout

    def run(self, task: SiteTask) -> SiteResult:
        result = SiteResult(task.name, task.site)
        t0 = time.time()
        started = datetime.now(UTC)
        try:
            self._run(task, result)
        except Exception as e:  # one broken site must not stop the gate
            result.outcome, result.why = "error", f"{type(e).__name__}: {e}"[:300]
        result.seconds = round(time.time() - t0, 1)
        calls, latencies, refused = llm_usage(started, datetime.now(UTC))
        result.llm_calls, result.decision_ms = calls, latencies
        if refused and not result.passed:
            result.why = f"{result.outcome}: {result.why or ''}"[:300]
            result.outcome = "quota"
        return result

    def _run(self, task: SiteTask, result: SiteResult) -> None:
        api = self.api
        api._sign_in()
        if task.account == "own" and not self._signed_in(task.target):
            result.outcome = "needs_sign_in"
            result.why = f"Sign in to {origin_of(task.target)} on {self.web_url}/sites first"
            return
        created = api._call("POST", "/tasks", {"prompt": task.prompt, "target_url": task.target})
        planned = api._wait(
            f"/tasks/{created['id']}", lambda t: t["status"] != "planning", time.perf_counter()
        )
        if planned["status"] != "planned":
            result.outcome = f"planning_{planned['status']}"
            result.why = planned.get("clarification_question") or json.dumps(planned.get("error"))[:300]
            return
        plan = api._call("GET", f"/plans/{planned['plan_id']}")
        approved = api._call("POST", f"/plans/{plan['id']}/approve", {"revision": plan["revision"]})
        run = self._follow(approved["id"], result)
        if run is None:
            return
        if run["status"] != "verified":
            result.outcome = run["status"]
            result.why = (run.get("error") or {}).get("message")
            return
        events = self._events(run["id"])
        completed = [e for e in events if e.get("type") == "run.completed"]
        result.workflow_id = completed[-1].get("workflow_id") if completed else None
        url, title = self._final_page(result.workflow_id)
        result.final_url = url
        if not matches(task.success, url, title):
            result.outcome, result.why = "wrong_page", f"ended on {url!r} ({title!r})"
            return
        result.outcome = "verified"
        self._replay(result)

    def _follow(self, run_id: str, result: SiteResult) -> dict[str, Any] | None:
        """Wait for the run to end, answering pauses. None if the run was given up (and cancelled)."""
        deadline = time.perf_counter() + self.timeout
        while time.perf_counter() < deadline:
            run = self.api._call("GET", f"/runs/{run_id}")
            if run["status"] in FINAL:
                return run
            if run["status"] == "paused":
                pause = self._last_pause(run_id)
                if pause.get("reason") == "destructive_action":
                    result.confirmations += 1
                    self.api._call("POST", f"/runs/{run_id}/confirm",
                                   {"step_seq": pause.get("step_seq", 1), "decision": "allow"})  # fmt: skip
                    continue
                result.takeovers += 1
                if not self.interactive or result.takeovers > 1:
                    self.api._call("POST", f"/runs/{run_id}/cancel")
                    result.outcome, result.why = "paused", f"paused for a human: {pause.get('reason')}"
                    return None
                print(f"   needs you ({pause.get('reason')}): {self.web_url}/runs/{run_id}/live", flush=True)
                while self.api._call("GET", f"/runs/{run_id}")["status"] == "paused":
                    time.sleep(3)
                continue
            time.sleep(2)
        self.api._call("POST", f"/runs/{run_id}/cancel")
        result.outcome, result.why = "failed", f"no end after {self.timeout:g} s"
        return None

    def _replay(self, result: SiteResult) -> None:
        """The stored tutorial once more, with no LLM: do it with new values if it has inputs, else
        reverify."""
        if result.workflow_id is None:
            result.replay = "skipped"
            return
        wid = result.workflow_id
        started = datetime.now(UTC)
        try:
            inputs = self.api._call("GET", f"/workflows/{wid}/inputs")
            values = {i["key"]: _fresh(i["example"]) for i in inputs.get("inputs", [])}
            if values:
                run = self.api._call(
                    "POST", f"/workflows/{wid}/run", {"revision": inputs["revision"], "inputs": values}
                )
            else:
                run = self.api._call("POST", f"/workflows/{wid}/reverify")
        except Exception:
            run = self.api._call("POST", f"/workflows/{wid}/reverify")
        followed = self._follow(run["id"], SiteResult(result.name, result.site))
        result.replay = "verified" if followed is not None and followed["status"] == "verified" else "failed"
        calls, _, _ = llm_usage(started, datetime.now(UTC))
        result.replay_llm_calls = calls

    def _signed_in(self, target: str) -> bool:
        profiles = self.api._call("GET", "/sites/profiles").get("items", [])
        return any(p.get("site") == origin_of(target) for p in profiles)

    def _events(self, run_id: str) -> list[dict[str, Any]]:
        return events_of(run_id)

    def _last_pause(self, run_id: str) -> dict[str, Any]:
        paused = [e for e in events_of(run_id) if e.get("type") == "run.paused"]
        return paused[-1] if paused else {}

    def _final_page(self, workflow_id: str | None) -> tuple[str | None, str | None]:
        if workflow_id is None:
            return None, None
        workflow = self.api._call("GET", f"/workflows/{workflow_id}")
        steps = workflow.get("steps") or []
        if not steps:
            return None, None
        observed = steps[-1].get("observed_state") or {}
        url, query = observed.get("url"), observed.get("query")
        return (f"{url}?{query}" if query else url), observed.get("title")


def _fresh(example: str) -> str:
    """A new value of the same shape as the recorded one, so a create step makes a new thing."""
    return f"{example}-r{int(time.time()) % 10000}"


# --- the database (llm_calls, run events) ------------------------------------------------------------


def _db(query: Any) -> Any:
    from app.db import create_engine, create_sessionmaker

    async def go() -> Any:
        engine = create_engine()
        try:
            async with create_sessionmaker(engine)() as s:
                return await query(s)
        finally:
            await engine.dispose()

    return asyncio.run(go())


QUOTA_REFUSED = "quota_exhausted"
"""`llm_calls.status` of an attempt the provider refused for quota (HTTP 429)."""


def llm_usage(since: datetime, until: datetime) -> tuple[int, list[int], bool]:
    """LLM calls (one per call, not per attempt), step-decision latencies, and whether any attempt was refused
    for quota, between two times."""
    from sqlalchemy import select

    from app.db import LLMCallRow

    async def q(s: Any) -> tuple[int, list[int], bool]:
        rows = list(await s.scalars(select(LLMCallRow).where(LLMCallRow.created_at.between(since, until))))
        calls = len({r.call_id for r in rows})
        decisions = [r.latency_ms for r in rows if r.job == "LLMDecision" and r.status == "ok"]
        return calls, decisions, any(r.status == QUOTA_REFUSED for r in rows)

    result: tuple[int, list[int], bool] = _db(q)
    return result


def requests_today(provider: str = "gemini") -> int:
    """The provider's requests so far on its quota day (midnight to midnight, Pacific time, like Gemini's
    free tier). Requests it refused for quota don't count against the quota."""
    from sqlalchemy import text

    sql = text(
        "select count(*) from llm_calls where provider = :provider and status <> :refused and created_at >= "
        "(date_trunc('day', now() at time zone 'America/Los_Angeles') at time zone 'America/Los_Angeles')"
    )

    async def q(s: Any) -> int:
        return int((await s.execute(sql, {"provider": provider, "refused": QUOTA_REFUSED})).scalar_one())

    result: int = _db(q)
    return result


def events_of(run_id: str) -> list[dict[str, Any]]:
    from uuid import UUID

    from app.db.repositories import event_payload, events_after

    async def q(s: Any) -> list[dict[str, Any]]:
        return [event_payload(r) for r in await events_after(s, UUID(run_id))]

    result: list[dict[str, Any]] = _db(q)
    return result


# --- report -------------------------------------------------------------------------------------------


RUN_AGAIN = ("not_run", "quota", "needs_sign_in")
"""Outcomes that aren't a verdict: a resumed gate runs these tasks again."""


def summary(results: list[SiteResult]) -> dict[str, Any]:
    ran = [r for r in results if r.outcome not in RUN_AGAIN]
    calls = [r.llm_calls for r in ran]
    decisions = [ms for r in ran for ms in r.decision_ms]
    return {
        "tasks": len(results),
        "ran": len(ran),
        "passed": sum(r.passed for r in results),
        "verified": sum(r.outcome == "verified" for r in results),
        "replays_verified": sum(r.replay == "verified" for r in results),
        "replays_with_llm_calls": sum(bool(r.replay_llm_calls) for r in results),
        "needs_sign_in": [r.name for r in results if r.outcome == "needs_sign_in"],
        "still_to_run": [r.name for r in results if r.outcome in ("not_run", "quota")],
        "median_llm_calls": statistics.median(calls) if calls else None,
        "decision_p50_ms": statistics.median(decisions) if decisions else None,
    }


def markdown(results: list[SiteResult]) -> str:
    s = summary(results)
    lines = [
        f"**{s['passed']}/{s['tasks']} passed** (verified, the right page, ≤ 1 takeover, replayed without "
        "an LLM call). "
        f"Median LLM calls per task: {s['median_llm_calls']}; decision p50: {s['decision_p50_ms']} ms.",
        "",
        "| Task | Site | Outcome | Takeovers | Confirms | LLM calls | Replay | Why |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        replay = f"{r.replay} ({r.replay_llm_calls} calls)" if r.replay else "—"
        mark = "✅" if r.passed else "❌"
        why = (r.why or "").replace("|", "/")[:120]
        lines.append(
            f"| {r.name} | {r.site} | {mark} {r.outcome} | {r.takeovers} | {r.confirmations} | {r.llm_calls} "
            f"| {replay} | {why} |"
        )
    return "\n".join(lines)


# --- several days on a free tier (#494) ---------------------------------------------------------------


def load_saved(path: Path) -> dict[str, SiteResult]:
    """The gate's results so far, by task name (empty when there are none)."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["name"]: SiteResult(**r) for r in data.get("results", [])}


def still_to_run(tasks: list[SiteTask], saved: dict[str, SiteResult]) -> list[SiteTask]:
    """The tasks without a verdict yet: never run, stopped by the quota, or waiting for a sign-in."""
    return [t for t in tasks if t.name not in saved or saved[t.name].outcome in RUN_AGAIN]


def quota_allows(used: int, daily: int, per_task: int) -> bool:
    """Is there room today for one more task? A task that runs out halfway proves nothing and wastes the
    calls it did make."""
    return daily - used >= per_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmarks.real_sites", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    parser.add_argument("--only", nargs="*", default=[], help="task names to run (default: all)")
    parser.add_argument("--account", choices=["none", "own", "all"], default="all")
    parser.add_argument(
        "--interactive", action="store_true", help="wait for the owner at a pause (1 takeover)"
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--out", type=Path, default=Path("benchmarks/results/real-sites"))
    parser.add_argument(
        "--fresh", action="store_true", help="start over (default: resume, skip tasks with a verdict)"
    )
    parser.add_argument(
        "--daily-calls", type=int, default=40, help="LLM requests per day (Gemini free tier: 20 x 2 models)"
    )
    parser.add_argument(
        "--per-task", type=int, default=15, help="requests one task needs; none starts with fewer left"
    )
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    gate_file = args.out / "gate.json"
    saved = {} if args.fresh else load_saved(gate_file)
    chosen = [t for t in load_tasks() if (not args.only or t.name in args.only)
              and (args.account == "all" or t.account == args.account)]  # fmt: skip
    tasks = still_to_run(chosen, saved)
    if saved:
        print(f"Resuming: {len(chosen) - len(tasks)} of {len(chosen)} tasks already have a verdict.")
    runner = RealSiteRunner(args.api_url, interactive=args.interactive)
    for task in tasks:
        used = requests_today()
        if not quota_allows(used, args.daily_calls, args.per_task):
            print(f"Stopping: {used} of {args.daily_calls} LLM requests used today (Pacific time); a task "
                  f"needs about {args.per_task}. Run again after midnight Pacific to resume.")  # fmt: skip
            break
        print(f"== {task.name}: {task.prompt}", flush=True)
        r = runner.run(task)
        saved[task.name] = r
        print(
            f"   -> {r.outcome} in {r.seconds} s, {r.llm_calls} LLM calls, replay {r.replay}: {r.why or ''}",
            flush=True,
        )
        write_results(args.out, gate_file, [saved[t.name] for t in load_tasks() if t.name in saved])
    results = [saved.get(t.name) or SiteResult(t.name, t.site) for t in load_tasks()]
    write_results(args.out, gate_file, results)
    print("\n" + markdown(results))
    return 0


def write_results(out: Path, gate_file: Path, results: list[SiteResult]) -> None:
    """After every task, so a stopped run keeps what it did."""
    data = {"summary": summary(results), "results": [asdict(r) for r in results]}
    gate_file.write_text(json.dumps(data, indent=1), encoding="utf-8")
    (out / "gate.md").write_text(markdown(results) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
