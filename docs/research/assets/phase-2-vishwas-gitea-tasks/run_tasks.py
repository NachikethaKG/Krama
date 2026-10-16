"""The 4 candidate tasks, run through Krama's real ActionExecutor (role/name locators, no planner, no vision).

Steps are written by hand the way a good plan would target them. Each trial starts from a fresh repo
(deleted + re-created with a README through the API). Success is checked through Gitea's API, never the UI.
Run from backend/:  uv run python ../docs/research/assets/phase-2-vishwas-gitea-tasks/run_tasks.py <trials>
"""
import asyncio, base64, json, sys, time, urllib.request
from playwright.async_api import async_playwright
from app.agent.executor import ActionExecutor
from app.config import get_settings
from app.contracts_gen.common_schema import Action, Target

BASE = "http://127.0.0.1:3001"
REPO = "krama-research-tasks"
S = get_settings()
U = S.gitea_demo_user
R = f"/{U}/{REPO}"

def api(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    auth = base64.b64encode(f"{U}:{S.gitea_demo_password}".encode()).decode()
    req = urllib.request.Request(BASE + "/api/v1" + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read(); return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, None

def step(type_: str, value: str | None = None, role: str | None = None, name: str | None = None, selector: str | None = None):
    return Action(type=type_, value=value), (Target(role=role, name=name, selector=selector) if role or selector else None)

TASKS = {
    "create-issue": ([
        step("navigate", R + "/issues"),
        step("click", role="link", name="New Issue"),
        step("fill", "Login page shows a blank screen", role="textbox", name="Title"),
        step("fill", "Steps: open /user/login on a small window.", role="textbox", name="Leave a comment"),
        step("click", role="button", name="Create Issue"),
    ], lambda: (lambda s, b: s == 200 and any(i["title"] == "Login page shows a blank screen" for i in b))(*api("GET", f"/repos{R}/issues?state=all&type=issues"))),
    "create-branch": ([
        step("navigate", R + "/branches"),
        step("click", role="button", name='Create new branch from "main"'),
        step("fill", "feature-docs", role="textbox", name="Branch Name *"),
        step("click", role="button", name="Confirm"),
    ], lambda: api("GET", f"/repos{R}/branches/feature-docs")[0] == 200),
    "add-file": ([
        step("navigate", R),
        step("click", role="button", name="Add File"),
        step("click", role="link", name="New File"),
        step("fill", "docs/notes.md", role="textbox", name="Name your file…"),
        step("fill", "# Notes\n\nFirst note.", role="textbox", name="Editor content"),
        step("click", role="button", name="Commit Changes"),
    ], lambda: (lambda s, b: s == 200 and "First note" in base64.b64decode(b["content"]).decode())(*api("GET", f"/repos{R}/contents/docs/notes.md"))),
    "repo-settings": ([
        step("navigate", R + "/settings"),
        step("fill", "Docs for the team", role="textbox", name="Description"),
        step("click", role="button", name="Update Settings"),
    ], lambda: api("GET", f"/repos{R}")[1]["description"] == "Docs for the team"),
}
# Same task, the first of the three "Update Settings" buttons targeted by CSS selector instead of role+name.
TASKS["repo-settings-selector"] = ([*TASKS["repo-settings"][0][:2],
    step("click", selector="form:has(textarea#description) button.primary")], TASKS["repo-settings"][1])
# Same task, role+name, with the Gemini vision fallback picking one of the three buttons (live LLM, 1 call/trial).
TASKS["repo-settings-vision"] = TASKS["repo-settings"]

async def trial(page, steps, vision=None) -> list[str]:
    ex = ActionExecutor(page, vision)
    log = []
    for action, target in steps:
        r = await ex.execute(action, target)
        log.append(f"{action.type} {(target.name or target.selector) if target else action.value!r}: {'ok' if r.ok else r.error.code} [{r.strategy}] {r.duration_ms}ms")
        if not r.ok:
            log.append(f"   {r.error.message[:200]}"); break
        await page.wait_for_load_state("domcontentloaded")
    return log

async def main() -> None:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    only = sys.argv[2].split(",") if len(sys.argv) > 2 else list(TASKS)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
        ctx.set_default_timeout(5_000)
        page = await ctx.new_page()
        await page.goto("/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(U)
        await page.get_by_role("textbox", name="Password").fill(S.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/")
        for name in only:
            steps, check = TASKS[name]
            passed = 0
            for t in range(trials):
                api("DELETE", f"/repos{R}")
                assert api("POST", "/user/repos", {"name": REPO, "auto_init": True, "readme": "Default"})[0] == 201
                t0 = time.perf_counter()
                vision = None
                if name.endswith("-vision"):
                    from app.agent.vision import GeminiVisionLocator
                    from app.llm import create_provider
                    vision = GeminiVisionLocator(create_provider(S))
                log = await trial(page, steps, vision)
                await page.wait_for_timeout(500)
                ok = bool(check()); passed += ok
                print(f"{name} trial {t + 1}: {'PASS' if ok else 'FAIL'} in {time.perf_counter() - t0:.1f}s")
                if not ok or t == 0:
                    print("   " + "\n   ".join(log))
            print(f"== {name}: {passed}/{trials}")
        await b.close()
    api("DELETE", f"/repos{R}")

if __name__ == "__main__":
    asyncio.run(main())
