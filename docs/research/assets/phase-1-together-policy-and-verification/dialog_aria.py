"""Open (never confirm) two Gitea delete dialogs on the throwaway fixture repo and show what the ARIA snapshot exposes."""
import asyncio
from playwright.async_api import async_playwright
from app.config import get_settings
R = "http://localhost:3001/demo/policy-fixture"
async def main() -> None:
    s = get_settings()
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto("http://localhost:3001/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url("http://localhost:3001/")
        for url, opener in [(R + "/branches", 'Delete Branch "feature-x"'), (R + "/settings", "Delete This Repository")]:
            await page.goto(url)
            await page.get_by_role("button", name=opener, exact=True).click()   # opens the modal only
            await page.wait_for_timeout(700)
            snap = await page.locator("body").aria_snapshot()
            lines = snap.splitlines()
            idx = [i for i, l in enumerate(lines) if ('button "Yes"' in l or 'button "Delete Repository"' in l)]
            for i in idx:
                print("   ARIA context:")
                for l in lines[max(0, i - 6): i + 2]:
                    print("      " + l)
            dialogs = page.get_by_role("dialog")
            print(f"--- after clicking {opener!r} (url still {page.url.replace('http://localhost:3001','')}), dialogs: {await dialogs.count()}")
            for i in range(await dialogs.count()):
                d = dialogs.nth(i)
                if await d.is_visible():
                    print(await d.aria_snapshot())
            yes = page.get_by_role("button", name="Yes", exact=True)
            print("   visible 'Yes' buttons on page:", sum([await yes.nth(i).is_visible() for i in range(await yes.count())]))
            await page.keyboard.press("Escape")
        await b.close()
asyncio.run(main())
