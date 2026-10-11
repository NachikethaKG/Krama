"""Read-only: what do Gitea's confirmation modals and a few extra pages contain? Nothing is clicked."""
import asyncio
from playwright.async_api import async_playwright
from app.config import get_settings
R = "/demo/policy-fixture"
JS = """() => [...document.querySelectorAll('.ui.modal')].map(m => ({
  id: m.id || m.className, header: (m.querySelector('.header')?.innerText || '').trim().slice(0, 70),
  buttons: [...m.querySelectorAll('button, .button')].map(b => (b.innerText || b.getAttribute('aria-label') || '').trim()).filter(Boolean),
  inputs: [...m.querySelectorAll('input:not([type=hidden])')].map(i => i.name || i.id)}))"""
EXTRA = """() => [...document.querySelectorAll('a, button, input[type=submit]')]
  .map(e => (e.getAttribute('aria-label') || e.getAttribute('data-tooltip-content') || e.innerText || e.value || '').trim().replace(/\s+/g,' '))
  .filter(n => /delete|remove|username|private|visib/i.test(n))"""
async def main() -> None:
    s = get_settings()
    async with async_playwright() as p:
        b = await p.chromium.launch(); page = await b.new_page()
        await page.goto("http://localhost:3001/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill(s.gitea_demo_user)
        await page.get_by_role("textbox", name="Password").fill(s.gitea_demo_password)
        await page.get_by_role("button", name="Sign In").click(); await page.wait_for_url("http://localhost:3001/")
        for path in [R + "/settings", R + "/branches", R + "/labels", R + "/milestones", R + "/issues/1", R + "/settings/hooks/1"]:
            await page.goto("http://localhost:3001" + path)
            for m in await page.evaluate(JS):
                if m["buttons"]:
                    print(f"{path.replace(R,'R'):20} modal {m['header']!r:72} buttons={m['buttons']} inputs={m['inputs']}")
        for path in ["/user/settings/account", "/user/settings", R + "/src/branch/main/README.md", R + "/releases/edit/v0.1", R + "/settings"]:
            await page.goto("http://localhost:3001" + path)
            names = sorted(set(await page.evaluate(EXTRA)))
            print(f"{path.replace(R,'R'):30} extra: {names}")
            if path.endswith("/settings"):
                print("   checkboxes:", await page.evaluate("() => [...document.querySelectorAll('input[type=checkbox]')].map(i => i.name + '=' + (i.closest('.field')?.innerText||'').trim().slice(0,40))"))
        await b.close()
asyncio.run(main())
