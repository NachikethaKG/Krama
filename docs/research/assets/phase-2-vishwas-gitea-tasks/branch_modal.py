"""What the 'Create new branch' modal looks like to ARIA (the branch task found its submit button only by text)."""
import asyncio
from playwright.async_api import async_playwright
import run_tasks as rt  # reuses login + API helpers

async def main() -> None:
    rt.api("DELETE", f"/repos{rt.R}"); rt.api("POST", "/user/repos", {"name": rt.REPO, "auto_init": True})
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page(viewport={"width": 1280, "height": 800})
        await page.goto(rt.BASE + "/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(rt.U)
        await page.get_by_role("textbox", name="Password").fill(rt.S.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url(rt.BASE + "/")
        await page.goto(rt.BASE + rt.R + "/branches")
        await page.get_by_role("button", name='Create new branch from "main"').click(); await page.wait_for_timeout(500)
        snap = await page.locator("body").aria_snapshot()
        print("\n".join(l for l in snap.splitlines() if "ranch" in l or "dialog" in l or "Cancel" in l or "Confirm" in l))
        print("text matches:", [await page.get_by_text("Create branch").nth(i).evaluate("e => e.outerHTML.slice(0, 120)") for i in range(await page.get_by_text("Create branch").count())])
        await b.close()
    rt.api("DELETE", f"/repos{rt.R}")

asyncio.run(main())
