"""Replay a stored Verified Workflow headlessly with its stored locators: no planner, no replan.

Uses Krama's real pieces: ActionExecutor (locator chain), PageObserver, LayeredVerifier, act_and_verify.
Scenarios on one stored "create a repository" workflow:
  as-stored     replay as is (the repository it created still exists)
  reset         delete that repository first, then replay
  renamed-name  the stored target name no longer exists ("New Repository" -> "Add Repository"), simulating a bad locator
  ui-renamed    the site's button text changes ("Create Repository" -> "Make repo"), stored locator unchanged
  ui-suffix     the label only grows ("Create Repository" -> "Create Repository now"): substring match tolerates it
Run from backend/:  uv run python ../docs/research/assets/phase-2-vishwas-reverify/reverify.py <workflow_id>
"""
import asyncio, base64, json, subprocess, sys, tempfile, time, urllib.request
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
from app.verifier.layered import LayeredVerifier

BASE = "http://127.0.0.1:3001"
S = get_settings()

def stored_steps(workflow_id: str) -> tuple[list[dict], str]:
    sql = (f"select json_build_object('steps', (select json_agg(json_build_object('seq', seq, 'action', action, 'target', target, "
           f"'instruction_text', instruction_text, 'expected_state', expected_state, 'risk', risk) order by seq) "
           f"from workflow_steps where workflow_id='{workflow_id}'), 'title', (select title from workflows where id='{workflow_id}'))")
    out = subprocess.run(["docker", "exec", "krama-postgres-1", "psql", "-U", "krama", "-d", "krama", "-At", "-c", sql],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    return d["steps"], d["title"]

def to_planned(row: dict) -> PlannedStep:
    target = {k: v for k, v in row["target"].items() if k in ("role", "name", "selector")}
    return PlannedStep(seq=row["seq"], action=row["action"], target=target or None, instruction_text=row["instruction_text"],
                       expected_state=row["expected_state"], risk=row["risk"])

def delete_repo(name: str) -> int:
    auth = base64.b64encode(f"{S.gitea_demo_user}:{S.gitea_demo_password}".encode()).decode()
    req = urllib.request.Request(f"{BASE}/api/v1/repos/{S.gitea_demo_user}/{name}", method="DELETE", headers={"Authorization": f"Basic {auth}"})
    try:
        return urllib.request.urlopen(req).status
    except urllib.error.HTTPError as e:
        return e.code

RENAME_JS = """(([from, to]) => { const fix = () => document.querySelectorAll('button').forEach(b => {
  if (b.textContent.trim() === from) b.textContent = to; });
  document.addEventListener('DOMContentLoaded', fix); })(%s)"""

async def replay(rows: list[dict], *, rename: tuple[str, str] | None = None) -> list[dict]:
    steps = [to_planned(r) for r in rows]
    report = []
    with tempfile.TemporaryDirectory() as tmp:
        async with async_playwright() as p:
            b = await p.chromium.launch()
            ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
            ctx.set_default_timeout(5_000)
            if rename:
                await ctx.add_init_script(RENAME_JS % json.dumps(list(rename)))
            page = await ctx.new_page()
            ex = ActionExecutor(page)
            await page.goto("/")
            log = await run_script(ex, login_steps(user=S.gitea_demo_user, password=S.gitea_demo_password), task="pre", base_url=BASE)
            assert log.ok, "sign-in failed"
            observer = PageObserver(artifact_store=LocalFsStore(Path(tmp)), run_id=str(uuid4()))
            failed = False
            for st in steps:
                if failed:
                    report.append({"seq": st.seq, "result": "not_run"}); continue
                t0 = time.perf_counter()
                out = await act_and_verify(st, ex, observer, LayeredVerifier(None), page, verify_timeout_s=5.0, verify_interval_s=0.25)
                v = out.verification.verification if out.verification else None
                report.append({"seq": st.seq, "target": st.target.model_dump(exclude_none=True) if st.target else None,
                               "action_ok": out.result.ok, "error": out.result.error.code if out.result.error else None,
                               "strategy": out.result.strategy, "result": v.result if v else "failed",
                               "observed_url": out.observed.url, "seconds": round(time.perf_counter() - t0, 1)})
                failed = not out.verified
            await b.close()
    return report

async def main() -> None:
    rows, title = stored_steps(sys.argv[1])
    repo = rows[-1]["expected_state"]["url_matches"].strip("^$").split("/")[-1]
    print(f"workflow: {title} ({len(rows)} steps), repo {repo}")
    renamed = json.loads(json.dumps(rows)); renamed[0]["target"]["name"] = "Add Repository"
    scenarios = {
        "as-stored": lambda: replay(rows),
        "reset": lambda: (delete_repo(repo), replay(rows))[1],
        "renamed-name": lambda: (delete_repo(repo), replay(renamed))[1],
        "ui-renamed": lambda: (delete_repo(repo), replay(rows, rename=("Create Repository", "Make repo")))[1],
        "ui-suffix": lambda: (delete_repo(repo), replay(rows, rename=("Create Repository", "Create Repository now")))[1],
    }
    results = {}
    for name, run in scenarios.items():
        results[name] = await run()
        print(f"== {name}")
        for r in results[name]:
            print("   ", json.dumps(r))
    Path(__file__).with_name("results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

asyncio.run(main())
