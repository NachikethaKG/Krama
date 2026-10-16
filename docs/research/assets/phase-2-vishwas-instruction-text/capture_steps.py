"""Build the instruction-text test set: real steps on live Gitea, with what a post-run rewrite could know.

For each step: action, role/name, value, URL path, bbox + viewport (-> coarse screen region) and the element's
context from the DOM (enclosing dialog / menu / nav / form section heading). Writes steps.json.
Run from backend/:  uv run python ../docs/research/assets/phase-2-vishwas-instruction-text/capture_steps.py
"""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright
from app.agent.executor import ActionExecutor
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "phase-2-vishwas-gitea-tasks"))
import run_tasks as rt

CONTEXT_JS = r"""el => {
  const dialog = el.closest('.ui.modal, [role=dialog]');
  const bar = el.closest('#navbar, .navbar');
  const menu = el.closest('.menu, [role=menu]');
  let container = null;
  if (dialog) container = 'dialog "' + ((dialog.querySelector('.header') || {}).textContent || '').trim() + '"';
  else if (bar) container = menu ? 'top bar menu' : 'top bar';
  else if (menu) container = 'dropdown menu';
  // Nearest visible heading before the element in document order (form section titles in Gitea are h4).
  let heading = null;
  const hs = [...document.querySelectorAll('h1, h2, h3, h4')].filter(h => h.offsetParent !== null);
  for (const h of hs) if (h.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) heading = h.textContent.trim().replace(/\s+/g, ' ');
  if (dialog) heading = null;
  return { container, section_heading: heading ? heading.replace(/ \d+$/, '').slice(0, 60) : null };
}"""

def region(bbox, vw, vh):
    x, y, w, h = bbox; cx, cy = x + w / 2, y + h / 2
    col = "left" if cx < vw / 3 else "right" if cx > 2 * vw / 3 else "center"
    row = "top" if cy < vh / 4 else "bottom" if cy > 3 * vh / 4 else "middle"
    return f"{row}-{col}"

CREATE_REPO = [
    rt.step("click", role="link", name="New Repository"),
    rt.step("fill", "team-docs", role="textbox", name="Repository Name *"),
    rt.step("click", role="checkbox", name="Initialize Repository"),
    rt.step("click", role="button", name="Create Repository"),
]

async def main() -> None:
    tasks = {"create-repo": CREATE_REPO, **{k: v[0] for k, v in rt.TASKS.items() if k in ("create-issue", "create-branch", "add-file", "repo-settings-selector")}}
    rows = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=rt.BASE); ctx.set_default_timeout(5_000)
        page = await ctx.new_page()
        await page.goto("/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(rt.U)
        await page.get_by_role("textbox", name="Password").fill(rt.S.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url(rt.BASE + "/")
        for task, steps in tasks.items():
            rt.api("DELETE", f"/repos/{rt.U}/team-docs")
            rt.api("DELETE", f"/repos{rt.R}"); rt.api("POST", "/user/repos", {"name": rt.REPO, "auto_init": True})
            await page.goto("/"); await page.get_by_role("main").wait_for()
            ex = ActionExecutor(page)
            for action, target in steps:
                path = ex.current_path()
                row = {"task": task, "action": action.type, "value": action.value, "page_path": path,
                       "page_title": await page.title()}
                if target:
                    # The executor's own locator chain, so the element is the one a run would act on.
                    loc, strategy = await ex._resolve(target, None, [])
                    await loc.scroll_into_view_if_needed()
                    row["found_by"] = strategy
                    row["real_role"] = await loc.evaluate("e => e.getAttribute('role') || e.tagName.toLowerCase()")
                    ctx_info = await loc.evaluate(CONTEXT_JS)
                    box = await loc.bounding_box()
                    row |= {"role": target.role or "button", "name": target.name or "Update Settings",
                            "region": region((box["x"], box["y"], box["width"], box["height"]), 1280, 800), **ctx_info}
                r = await ex.execute(action, target)
                assert r.ok, (task, action, r.error)
                await page.wait_for_load_state("domcontentloaded"); await page.wait_for_timeout(300)
                rows.append(row)
        await b.close()
    rt.api("DELETE", f"/repos{rt.R}"); rt.api("DELETE", f"/repos/{rt.U}/team-docs")
    (HERE / "steps.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))

asyncio.run(main())
