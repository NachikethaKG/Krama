"""Which expected-state conditions catch a step that 'ran' but had no effect?
Real ActionExecutor + PageObserver + RuleVerifier on local Gitea. The broken case: create a repository whose name is
already taken. Every action succeeds (fill, tick, click), but no repository is created."""
import asyncio, tempfile
from pathlib import Path
from playwright.async_api import async_playwright
from app.agent.executor import ActionExecutor
from app.config import get_settings
from app.contracts_gen.common_schema import Action, ElementRef, ExpectedState, Target
from app.observer import PageObserver
from app.verifier import RuleVerifier

CASES = {  # expected state after clicking "Create Repository"
    "title only (weak)":                ExpectedState(title_contains="Gitea"),
    "button still visible (weak)":      ExpectedState(visible=[ElementRef(role="button", name="Create Repository")]),
    "url = new repo (strong)":          ExpectedState(url_matches=r"^/demo/policy-fixture$"),
    "error absent, wrong role 'text'":   ExpectedState(absent=[ElementRef(role="text", name="The repository name is already used")]),
    "error absent, role 'paragraph'":   ExpectedState(absent=[ElementRef(role="paragraph", name="The repository name is already used")]),
    "nav link visible (outside main)":  ExpectedState(visible=[ElementRef(role="link", name="Explore")]),
    "heading of new repo visible":      ExpectedState(visible=[ElementRef(role="link", name="policy-fixture")]),
}

async def main() -> None:
    s = get_settings(); v = RuleVerifier()
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page(viewport={"width": 1280, "height": 800})
        ex = ActionExecutor(page)
        obs = PageObserver(artifacts_dir=Path(tempfile.mkdtemp()))
        base = "http://localhost:3001"
        await page.goto(base + "/user/login")
        await ex.execute(Action(type="fill", value=s.gitea_demo_user), Target(role="textbox", name="Username or Email Address"))
        await ex.execute(Action(type="fill", value=s.gitea_demo_password), Target(role="textbox", name="Password"))
        await ex.execute(Action(type="click"), Target(role="button", name="Sign In"))
        await page.wait_for_url(base + "/")
        await page.goto(base + "/repo/create")
        results = [await ex.execute(Action(type="fill", value="policy-fixture"), Target(role="textbox", name="Repository Name *")),
                   await ex.execute(Action(type="click"), Target(role="button", name="Create Repository"))]
        print("actions ok:", [r.ok for r in results], "| url after:", page.url.replace(base, ""))
        observed = await obs.capture(page)
        print("--- excerpt lines with 'already' or 'Explore':", [l for l in observed.aria_excerpt.splitlines() if "already" in l or "Explore" in l])
        for name, exp in CASES.items():
            out = v.verify(exp, observed)
            print(f"  {name:32} -> {out.verification.result:8} via {out.verification.method}")
        await b.close()
asyncio.run(main())
