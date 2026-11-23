"""Phase 7 spike (#457), Part A: today's Krama on sites it has no notes for, through the product path.

Signs in like the benchmark (demo account from the repo-root .env), then for each task: POST /tasks, wait for the
plan, approve it, wait for the run. A paused run is recorded and cancelled (nobody answers in the spike).
Writes one JSON file per task to the output directory. Run from the repo root:

    uv run --project backend python <path>/part_a.py <out_dir> [task_id ...]
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path.cwd()))
from benchmarks.api_runner import FINAL, ApiAgentRunner  # noqa: E402

TASKS: list[dict[str, str]] = [
    {
        "id": "wikipedia-search",
        "url": "https://en.wikipedia.org",
        "prompt": "Search Wikipedia for Alan Turing and open his article",
    },
    {
        "id": "osm-search",
        "url": "https://www.openstreetmap.org",
        "prompt": "Search the map for Bengaluru",
    },
    {
        "id": "todomvc-add-complete",
        "url": "https://demo.playwright.dev/todomvc",
        "prompt": "Add a todo called Buy milk and mark it as completed",
    },
    {
        "id": "python-docs-search",
        "url": "https://docs.python.org/3",
        "prompt": "Search the Python documentation for asyncio.gather and open its entry",
    },
    {
        "id": "mdn-nav",
        "url": "https://developer.mozilla.org/en-US",
        "prompt": "Find the MDN reference page for the JavaScript Array.prototype.map method",
    },
]


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    wanted = set(sys.argv[2:])
    for task in TASKS:
        if wanted and task["id"] not in wanted:
            continue
        print(f"== {task['id']}", flush=True)
        result = run_one(task)
        (out / f"{task['id']}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"   -> {result['outcome']} in {result['seconds']} s: {result.get('why')}", flush=True)


def run_one(task: dict[str, str]) -> dict[str, Any]:
    r = ApiAgentRunner(target_url=task["url"], timeout=600.0, poll_s=2.0)
    t0 = time.time()
    result: dict[str, Any] = {"task": task, "started": round(t0, 1)}

    def done(outcome: str, why: Any = None) -> dict[str, Any]:
        result.update({"outcome": outcome, "why": why, "seconds": round(time.time() - t0, 1), "ended": round(time.time(), 1)})
        return result

    r._sign_in()
    created = r._call("POST", "/tasks", {"prompt": task["prompt"], "target_url": task["url"]})
    planned = r._wait(f"/tasks/{created['id']}", lambda t: t["status"] != "planning", time.perf_counter())
    result["task_row"] = planned
    if planned["status"] != "planned":
        return done(f"planning_{planned['status']}", planned.get("clarification_question") or planned.get("error"))
    plan = r._call("GET", f"/plans/{planned['plan_id']}")
    result["plan"] = plan
    run = r._call("POST", f"/plans/{plan['id']}/approve", {"revision": plan["revision"]})
    run = r._wait(f"/runs/{run['id']}", lambda x: x["status"] in (*FINAL, "paused"), time.perf_counter())
    result["run"] = run
    if run["status"] == "paused":
        r._call("POST", f"/runs/{run['id']}/cancel")
        return done("paused", run.get("pause") or run.get("error"))
    return done(run["status"], (run.get("error") or {}).get("message"))


if __name__ == "__main__":
    main()
