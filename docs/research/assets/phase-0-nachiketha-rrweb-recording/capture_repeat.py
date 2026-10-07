"""B) Re-check first-call outliers: screenshot(mask=) and long full_page, 4 repetitions each, fresh browser."""
import asyncio, time, json
from playwright.async_api import async_playwright

async def main():
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 1280, "height": 800})
        page = await ctx.new_page()
        await page.goto("http://localhost:3001/user/login")
        await page.get_by_role("textbox", name="Password").fill("demo-local-only")
        for label, fn in [("plain_jpeg", lambda: page.screenshot(type="jpeg", quality=70)),
                          ("mask_jpeg", lambda: page.screenshot(type="jpeg", quality=70, mask=[page.locator("input[type=password]")]))]:
            ts = []
            for _ in range(4):
                s = time.perf_counter(); await fn(); ts.append(round((time.perf_counter() - s) * 1000))
            out[label] = ts
        await page.set_content("<body style='margin:0'>" + "".join(f"<p style='height:40px;background:hsl({i % 360},60%,80%)'>row {i}</p>" for i in range(500)) + "</body>")
        for label, fn in [("long_png_full", lambda: page.screenshot(full_page=True)), ("long_jpeg_full", lambda: page.screenshot(full_page=True, type="jpeg", quality=70)),
                          ("long_jpeg_viewport", lambda: page.screenshot(type="jpeg", quality=70))]:
            ts = []
            for _ in range(3):
                s = time.perf_counter(); await fn(); ts.append(round((time.perf_counter() - s) * 1000))
            out[label] = ts
        await b.close()
    print(json.dumps(out))
asyncio.run(main())
