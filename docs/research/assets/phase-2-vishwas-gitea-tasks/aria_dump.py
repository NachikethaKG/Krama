"""ARIA snapshots of the pages the 4 new tasks go through, on a fresh repo with a README (created by API)."""
import asyncio, base64, json, sys, urllib.request
from pathlib import Path
from playwright.async_api import async_playwright
from app.config import get_settings

BASE = "http://127.0.0.1:3001"
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
REPO = "krama-research-tasks"

def api(method: str, path: str, body: dict | None = None) -> int:
    s = get_settings()
    auth = base64.b64encode(f"{s.gitea_demo_user}:{s.gitea_demo_password}".encode()).decode()
    req = urllib.request.Request(BASE + "/api/v1" + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req).status
    except urllib.error.HTTPError as e:
        return e.code

async def main() -> None:
    s = get_settings()
    print("delete", api("DELETE", f"/repos/{s.gitea_demo_user}/{REPO}"))
    print("create", api("POST", "/user/repos", {"name": REPO, "auto_init": True, "readme": "Default"}))
    r = f"/{s.gitea_demo_user}/{REPO}"
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1280, "height": 800})
        await page.goto(BASE + "/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/")
        for key, path in {"repo-home": r, "issues-new": r + "/issues/new", "branches": r + "/branches",
                          "new-file": r + "/_new/main/", "settings": r + "/settings"}.items():
            await page.goto(BASE + path); await page.get_by_role("main").wait_for(); await page.wait_for_timeout(800)
            (OUT / f"{key}.aria.yaml").write_text(await page.locator("body").aria_snapshot(), encoding="utf-8")
            await page.screenshot(path=str(OUT / f"{key}.png"))
            print(key, "ok")
        await b.close()

asyncio.run(main())
