"""B) Gotchas: full_page on a long page, aria snapshot leaking filled inputs, screenshot mask= cost."""

import asyncio
import json
import time

from playwright.async_api import async_playwright

BASE = "http://localhost:3001"


async def t(fn):
    s = time.perf_counter()
    out = await fn()
    return round((time.perf_counter() - s) * 1000, 1), out


async def main():
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
        page = await ctx.new_page()
        await page.goto("/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill("demo")
        await page.get_by_role("textbox", name="Password").fill("demo-local-only")
        aria = await page.get_by_role("main").first.aria_snapshot()
        res["login_aria_contains_password"] = "demo-local-only" in aria
        res["login_aria_contains_username"] = "demo" in aria
        res["login_aria"] = aria
        pw = page.locator("input[type=password]")
        ms, png = await t(lambda: page.screenshot(type="jpeg", quality=70, mask=[pw]))
        res["jpeg_with_mask_password_ms"] = ms
        ms, png = await t(lambda: page.screenshot(type="jpeg", quality=70, mask=[page.locator("input[type=password], input[autocomplete*=cc-]")]))
        res["jpeg_with_mask_selector_ms"] = ms
        (__import__("pathlib").Path(__file__).parent / "out" / "login_masked.jpg").write_bytes(png)

        for url in ["/api/swagger"]:
            await page.goto(url)
            await page.wait_for_timeout(1500)
            h = await page.evaluate("document.documentElement.scrollHeight")
            ms, full = await t(lambda: page.screenshot(full_page=True))
            ms2, fullj = await t(lambda: page.screenshot(full_page=True, type="jpeg", quality=70))
            ms3, vp = await t(lambda: page.screenshot(type="jpeg", quality=70))
            res[url] = {"doc_height": h, "png_full": [ms, len(full)], "jpeg70_full": [ms2, len(fullj)], "jpeg70_viewport": [ms3, len(vp)]}
        await page.set_content("<body style='margin:0'>" + "".join(
            f"<p style='height:40px;background:hsl({i % 360},60%,80%)'>row {i}</p>" for i in range(500)) + "</body>")
        h = await page.evaluate("document.documentElement.scrollHeight")
        ms, full = await t(lambda: page.screenshot(full_page=True))
        ms2, fullj = await t(lambda: page.screenshot(full_page=True, type="jpeg", quality=70))
        res["synthetic_long"] = {"doc_height": h, "png_full": [ms, len(full)], "jpeg70_full": [ms2, len(fullj)]}
        await b.close()
    print(json.dumps(res, indent=1))


asyncio.run(main())
