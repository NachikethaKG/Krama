"""A) Size effect of rrweb options on Gitea pages + FullSnapshot cost. Read-only (no repo creation)."""

import asyncio
import gzip
import json
import lzma
import time

from playwright.async_api import async_playwright

from rr_inject import Sink, build_init_script

BASE = "http://localhost:3001"
BASEOPTS = {"recordAfter": "DOMContentLoaded", "sampling": {"mousemove": 50, "scroll": 150, "input": "last"}}
CONFIGS = {
    "baseline(slimDOM all, inlineCSS)": {**BASEOPTS, "slimDOMOptions": "all"},
    "no slimDOM": {**BASEOPTS},
    "inlineStylesheet=false": {**BASEOPTS, "slimDOMOptions": "all", "inlineStylesheet": False},
    "checkoutEveryNms=3000": {**BASEOPTS, "slimDOMOptions": "all", "checkoutEveryNms": 3000},
}


async def run(name, opts, p):
    sink = Sink()
    b = await p.chromium.launch()
    ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
    await ctx.expose_binding("__krama_rr", sink.handler)
    await ctx.add_init_script(script=build_init_script("batch", opts, 200))
    page = await ctx.new_page()
    await page.goto("/user/login")
    await page.get_by_role("textbox", name="Username or Email Address").fill("demo")
    await page.get_by_role("textbox", name="Password").fill("demo-local-only")
    await page.get_by_role("button", name="Sign In").click()
    await page.wait_for_url(BASE + "/")
    snap_ms = []
    for path in ["/", "/repo/create", "/demo/rec-test-1"]:
        if path != "/":
            await page.goto(path)
        await page.mouse.move(300, 300, steps=10)
        await asyncio.sleep(7)
        snap_ms.append(await page.evaluate(
            "() => { const t = performance.now(); rrwebRecord.record.takeFullSnapshot(); return +(performance.now() - t).toFixed(1); }"))
    await page.evaluate("window.__kramaRR.flush()")
    await asyncio.sleep(0.3)
    await b.close()
    ev = sink.all_events()
    blob = json.dumps(ev, separators=(",", ":")).encode()
    return {"config": name, "events": len(ev), "full_snapshots": sum(e["type"] == 2 for e in ev), "json_bytes": len(blob),
            "gzip6": len(gzip.compress(blob, 6)), "xz(long window)": len(lzma.compress(blob, preset=6)),
            "takeFullSnapshot_ms(/, create, repo)": snap_ms}


async def main():
    async with async_playwright() as p:
        res = [await run(n, o, p) for n, o in CONFIGS.items()]
    print(json.dumps(res, indent=2))


asyncio.run(main())
