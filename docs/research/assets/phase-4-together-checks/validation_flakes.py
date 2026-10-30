"""How often does a validation replay fail when nothing on the site changed? And does a drifted one fail every time?

Replays the newest stored Gitea workflow of each benchmark task N times with Krama's real pieces: the target's
reset hook (`targets._gitea_reset`), sign-in, `ActionExecutor` (no vision: no LLM calls), `PageObserver`,
`LayeredVerifier` (no vision) and `runs.steps.act_and_verify`, with the run defaults (action timeout 5 s, verify
timeout 5 s). It stops at the first failed step and classifies it like `RunExecutor._fail_reverify`
(locator_miss / action_failed / state_mismatch).

Then one drift control: the "create repository" workflow with Gitea's "Create Repository" button renamed by an
init script, replayed N times, to see that real drift fails consistently (same step, same reason).

Run from backend/:  uv run python ../docs/research/assets/phase-4-together-checks/validation_flakes.py [N]
Output: results-flakes.json next to this script.
"""

import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from playwright.async_api import async_playwright

from app.agent.executor import ActionExecutor
from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import run_script
from app.config import get_settings
from app.contracts_gen.plan_schema import PlannedStep
from app.observer.observer import PageObserver
from app.runs.steps import act_and_verify
from app.storage.local import LocalFsStore
from app.targets import _gitea_reset
from app.verifier.layered import LayeredVerifier

BASE = "http://127.0.0.1:3001"
OUT = Path(__file__).with_name("results-flakes.json")
S = get_settings()

SQL = """select json_agg(x order by x.title) from (
  select distinct on (w.title) w.id, w.title,
    (select json_agg(json_build_object('seq', s.seq, 'action', s.action, 'target', s.target,
       'instruction_text', s.instruction_text, 'expected_state', s.expected_state, 'risk', s.risk,
       'before_state', s.before_state) order by s.seq) from workflow_steps s where s.workflow_id = w.id) steps
  from workflows w
  where w.status = 'verified' and w.target_app = 'gitea'
    and w.title in (select title from workflows group by title having count(*) >= 5)
  order by w.title, w.created_at desc) x"""

RENAME_JS = """document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('button').forEach(b => {
  if (b.textContent.trim() === 'Create Repository') b.textContent = 'Make repo'; }));"""


def workflows() -> list[dict]:
    out = subprocess.run(
        ["docker", "exec", "krama-postgres-1", "psql", "-U", "krama", "-d", "krama", "-At", "-c", SQL],
        capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout
    return json.loads(out)


def planned(row: dict) -> PlannedStep:
    target = {k: v for k, v in (row["target"] or {}).items() if k in ("role", "name", "selector") and v}
    return PlannedStep(seq=row["seq"], action=row["action"], target=target,
                       instruction_text=row["instruction_text"], expected_state=row["expected_state"], risk=row["risk"])


async def replay(browser, wf: dict, drift: str | None) -> dict:
    t0 = time.perf_counter()
    reset = await _gitea_reset(wf["steps"], S)
    ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
    ctx.set_default_timeout(5_000)
    ctx.set_default_navigation_timeout(15_000)
    if drift:
        await ctx.add_init_script(drift)
    page = await ctx.new_page()
    ex = ActionExecutor(page)
    await page.goto("/")
    log = await run_script(ex, login_steps(user=S.gitea_demo_user, password=S.gitea_demo_password),
                           task="pre", base_url=BASE)
    result = {"outcome": "passed", "reset": len(reset)}
    if not log.ok:
        result["outcome"] = "sign_in_failed"
    else:
        with tempfile.TemporaryDirectory() as tmp:
            observer = PageObserver(artifact_store=LocalFsStore(Path(tmp)), run_id=str(uuid4()))
            for row in wf["steps"]:
                out = await act_and_verify(planned(row), ex, observer, LayeredVerifier(None), page,
                                           verify_timeout_s=5.0, verify_interval_s=0.25)
                if out.verified:
                    continue
                err = out.result.error
                reason = ("locator_miss" if err and err.code in ("target_not_found", "ambiguous_target")
                          else "action_failed" if err else "state_mismatch")
                result.update(outcome="failed", step=row["seq"], reason=reason, error=err.code if err else None,
                              url=out.observed.url)
                break
    await ctx.close()
    result["seconds"] = round(time.perf_counter() - t0, 1)
    return result


async def main(n: int) -> None:
    wfs = workflows()
    results: dict = {"replays_per_workflow": n, "no_drift": [], "drift_control": []}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for wf in wfs:
            runs = [await replay(browser, wf, None) for _ in range(n)]
            results["no_drift"].append({"workflow": wf["id"], "title": wf["title"], "steps": len(wf["steps"]),
                                        "runs": runs})
            print(f'{wf["title"][:60]:60} {[r["outcome"] + (":" + r["reason"] if "reason" in r else "") for r in runs]}')
        repo = next(w for w in wfs if w["title"].startswith("Create a new public repository"))
        runs = [await replay(browser, repo, RENAME_JS) for _ in range(n)]
        results["drift_control"] = {"workflow": repo["id"], "drift": "Create Repository -> Make repo", "runs": runs}
        print("drift control:", [f'{r["outcome"]}:{r.get("reason")}@{r.get("step")}' for r in runs])
        await browser.close()
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 4))
