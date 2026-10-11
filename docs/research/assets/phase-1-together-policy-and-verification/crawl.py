"""Read-only crawl of Gitea 1.22 pages: list every control whose label contains a risky verb.
Only page.goto() is used: nothing is clicked or submitted. Hidden controls (inside closed confirmation modals) are
included with visible=False, together with their form's method/action, which shows what a click would really do."""
import asyncio, json, re, sys
from playwright.async_api import async_playwright
from app.config import get_settings

R = "/demo/policy-fixture"
PAGES = [R, R + "/settings", R + "/settings/collaboration", R + "/settings/branches", R + "/settings/hooks",
         R + "/settings/keys", R + "/branches", R + "/releases", R + "/issues/1", R + "/labels", R + "/milestones",
         R + "/src/branch/main/README.md", R + "/settings/hooks/1",
         "/user/settings", "/user/settings/account", "/user/settings/security", "/user/settings/applications",
         "/user/settings/keys", "/user/settings/repos", "/notifications", "/"]
VERBS = re.compile(r"\b(delete|remove|transfer|archive|unarchive|convert|reset|regenerate|revoke|disable|close|lock|"
                   r"private|public|visibility|leave|block|unwatch|unstar|force|merge|drop|clear|discard|rename|"
                   r"change username|sign out|deactivate|purge|unlink|cancel|update password|mirror)\b", re.I)
JS = """() => [...document.querySelectorAll('button, a, input[type=submit], [role=menuitem], .item.link-action, .delete-button')]
  .map(e => {
    const name = (e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('data-tooltip-content') || '').trim().replace(/\s+/g, ' ');
    const f = e.closest('form');
    const r = e.getBoundingClientRect();
    return {tag: e.tagName.toLowerCase(), name: name.slice(0, 80), visible: !!(r.width && r.height) && getComputedStyle(e).visibility !== 'hidden',
            href: e.getAttribute('href'), data_url: e.getAttribute('data-url') || e.getAttribute('data-modal-id') || null,
            form: f ? (f.getAttribute('method') || 'get').toUpperCase() + ' ' + (f.getAttribute('action') || '') : null,
            modal: !!e.closest('.ui.modal')};
  })"""

async def main() -> None:
    s = get_settings(); out = []
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page(viewport={"width": 1280, "height": 800})
        await page.goto("http://localhost:3001/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url("http://localhost:3001/")
        for path in PAGES:
            resp = await page.goto("http://localhost:3001" + path)
            await page.wait_for_timeout(300)
            seen = set()
            for el in await page.evaluate(JS):
                if el["name"] and VERBS.search(el["name"]) and (el["name"], el["form"], el["href"]) not in seen:
                    seen.add((el["name"], el["form"], el["href"]))
                    out.append({"page": path, **el})
            print(f"{resp.status if resp else '?'} {path}: {len(seen)} risky-verb controls", flush=True)
        await b.close()
    open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(out, indent=1, ensure_ascii=False))
asyncio.run(main())
