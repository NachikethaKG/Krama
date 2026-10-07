import asyncio

from playwright.async_api import async_playwright

from rr_inject import Sink, build_init_script


async def main():
    sink = Sink()
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context()
        await ctx.expose_binding("__krama_rr", sink.handler)
        await ctx.add_init_script(script=build_init_script("per", {"recordAfter": "DOMContentLoaded"}))
        page = await ctx.new_page()
        page.on("console", lambda m: print("console:", m.type, m.text[:300]))
        page.on("pageerror", lambda e: print("pageerror:", e))
        await page.goto("http://localhost:3001/user/login")
        await asyncio.sleep(1)
        print(await page.evaluate("[typeof rrwebRecord, typeof window.__kramaRR, typeof window.__krama_rr, window.__kramaRR && window.__kramaRR.stats()]"))
        print("calls", sink.calls)
        await b.close()

asyncio.run(main())
