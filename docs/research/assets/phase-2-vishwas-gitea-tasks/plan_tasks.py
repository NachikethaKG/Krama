"""Can the real planner (live Gemini, today's prompt and site hints) plan the 4 new tasks from the dashboard?

Same start as PlanningService: signed in, on "/", ARIA snapshot of that page only. Each plan is then executed
by the ActionExecutor (no verifier, no replan) and checked through Gitea's API.
Run from backend/:  uv run python ../docs/research/assets/phase-2-vishwas-gitea-tasks/plan_tasks.py <out.json>
"""
import asyncio, json, sys, uuid
from pathlib import Path
from playwright.async_api import async_playwright
from app.agent.executor import ActionExecutor
from app.llm import create_provider
from app.planner.planner import LLMPlanner, PlanRequest, PlannerError
from app.planner.service import page_snapshot
sys.path.insert(0, str(Path(__file__).parent))
import run_tasks as rt

PROMPTS = {
    "create-issue": (f"In the repository {rt.REPO}, open an issue titled 'Login page shows a blank screen'.", rt.TASKS["create-issue"][1]),
    "create-branch": (f"Create a branch named feature-docs from main in the repository {rt.REPO}.", rt.TASKS["create-branch"][1]),
    "add-file": (f"Add a file docs/notes.md containing 'First note' to the main branch of {rt.REPO}.", rt.TASKS["add-file"][1]),
    "repo-settings": (f"Set the description of the repository {rt.REPO} to 'Docs for the team'.", rt.TASKS["repo-settings"][1]),
}

# Experimental hints for the 4 flows (only used with --hints). They describe pages the planner can't see yet.
HINTS = "\n".join([
    "Repository pages are at /<owner>/<repo>; navigate there directly instead of clicking dashboard links.",
    "New issue: /<owner>/<repo>/issues/new has textbox \"Title\", textbox \"Leave a comment\" and button",
    "\"Create Issue\". After creation the URL is /<owner>/<repo>/issues/<number>.",
    "New branch: /<owner>/<repo>/branches has button 'Create new branch from \"main\"'. It opens a dialog with",
    "textbox \"Branch Name *\" and button \"Confirm\". After creation the URL is /<owner>/<repo>/src/branch/<name>.",
    "New file: /<owner>/<repo>/_new/<branch>/ has textbox \"Name your file…\" (a path like docs/a.md is allowed),",
    "textbox \"Editor content\" for the file content and button \"Commit Changes\". After the commit the URL is",
    "/<owner>/<repo>/src/branch/<branch>/<path>.",
    "Repository settings: /<owner>/<repo>/settings has textbox \"Description\". The page has THREE buttons named",
    "\"Update Settings\"; the one that saves the description has selector form:has(textarea#description) button.primary.",
    "After saving, the page stays on /<owner>/<repo>/settings.",
])

async def main() -> None:
    out = {}
    if "--hints" in sys.argv:
        from app.planner import prompt
        prompt.SITE_HINTS["gitea"] = prompt.SITE_HINTS["gitea"] + "\n" + HINTS
    planner = LLMPlanner(create_provider(rt.S))
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=rt.BASE); ctx.set_default_timeout(5_000)
        page = await ctx.new_page()
        await page.goto("/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(rt.U)
        await page.get_by_role("textbox", name="Password").fill(rt.S.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url(rt.BASE + "/")
        for key, (prompt, check) in PROMPTS.items():
            rt.api("DELETE", f"/repos{rt.R}"); rt.api("POST", "/user/repos", {"name": rt.REPO, "auto_init": True})
            await page.goto("/"); await page.get_by_role("main").wait_for()
            req = PlanRequest(task_id=uuid.uuid4(), task=prompt, start_path="/", page_snapshot=await page_snapshot(page),
                              site="gitea", signed_in_as=rt.U)
            try:
                res = await planner.plan(req)
            except PlannerError as e:
                print(f"{key}: planner error {e}"); out[key] = {"error": str(e)}; continue
            steps = res.plan.steps
            ex, log = ActionExecutor(page), []
            for st in steps:
                r = await ex.execute(st.action, st.target, instruction=st.instruction_text)
                log.append({"seq": st.seq, "instruction_text": st.instruction_text, "action": st.action.model_dump(),
                            "target": st.target.model_dump() if st.target else None, "ok": r.ok, "strategy": r.strategy,
                            "error": r.error.model_dump() if r.error else None})
                if not r.ok:
                    break
                await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(500)
            ok = bool(check())
            out[key] = {"model": res.model, "passed": ok, "steps": log}
            print(f"{key}: {'PASS' if ok else 'FAIL'} ({res.model}, {len(steps)} steps)")
            for s in log:
                print(f"   {s['seq']}. {s['instruction_text']}  -> {s['action']['type']} {s['target']} {'ok' if s['ok'] else s['error']}")
        await b.close()
    rt.api("DELETE", f"/repos{rt.R}")
    Path(sys.argv[1]).write_text(json.dumps(out, indent=2), encoding="utf-8")

asyncio.run(main())
