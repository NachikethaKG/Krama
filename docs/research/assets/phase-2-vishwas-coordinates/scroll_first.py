"""Fix candidate: scroll_into_view_if_needed() BEFORE measuring, so the stored scroll is the one the click uses.
Also lists position:fixed/sticky elements on common Gitea pages (their page coordinates move with the scroll)."""
import asyncio, json
from playwright.async_api import async_playwright
from app.config import get_settings

BASE = "http://127.0.0.1:3001"
TARGETS = [("checkbox", "Make repository a template"), ("textbox", "Default Branch"), ("checkbox", "Make repository private")]
FIXED_JS = """[...document.querySelectorAll('*')].filter(e => ['fixed','sticky'].includes(getComputedStyle(e).position)
  && e.getBoundingClientRect().height > 0).map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + [...e.classList].join('.') + ' ' + getComputedStyle(e).position)"""

async def main() -> None:
    s = get_settings()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1280, "height": 600})
        await page.goto(BASE + "/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/")
        await page.goto(BASE + "/repo/create"); await page.get_by_role("main").wait_for()
        for role, name in TARGETS:
            loc = page.get_by_role(role, name=name, exact=True)
            await loc.scroll_into_view_if_needed()
            box = await loc.bounding_box(); sx, sy = await page.evaluate("[scrollX, scrollY]")
            await loc.click(); await page.wait_for_timeout(200)
            sx2, sy2 = await page.evaluate("[scrollX, scrollY]")
            print(json.dumps({"target": name, "viewport_box": [box["x"], box["y"]], "scroll_measured": [sx, sy],
                              "scroll_after_click": [sx2, sy2], "same": [sx, sy] == [sx2, sy2]}))
        for path in ["/", "/repo/create", "/demo/demo-repo", "/demo/demo-repo/settings", "/demo/demo-repo/issues/new"]:
            await page.goto(BASE + path); await page.get_by_role("main").wait_for(); await page.wait_for_timeout(500)  # never networkidle: Gitea keeps a long-poll open
            print(path, await page.evaluate(FIXED_JS))
        await b.close()

asyncio.run(main())
