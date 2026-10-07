"""B) Per-step page-state capture cost on Gitea: screenshots, aria snapshot, title/url, network summary.

Read-only (visits existing pages). 5 repetitions per measurement, reports median ms.
"""

import asyncio
import json
import statistics
import time
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

BASE = "http://localhost:3001"
PAGES = ["/", "/repo/create", "/demo/rec-test-2"]
N = 5


class NetLog:
    """Collects a compact per-step network summary from page events."""

    def __init__(self, page):
        self.items, self.start = [], {}
        page.on("request", self.on_req)
        page.on("response", self.on_resp)
        page.on("requestfailed", self.on_fail)
        page.on("requestfinished", self.on_done)

    def reset(self):
        self.items, self.start = [], {}

    def on_req(self, r):
        self.start[r] = time.perf_counter()

    def _add(self, r, status, failure=None):
        t0 = self.start.get(r)
        u = urlsplit(r.url)
        self.items.append([r.method, u.path + ("?" + u.query[:40] if u.query else ""), status, r.resource_type,
                           round((time.perf_counter() - t0) * 1000) if t0 else None] + ([failure] if failure else []))

    def on_resp(self, resp):
        self.status = getattr(self, "status", {})
        self.status[resp.request] = resp.status

    def on_done(self, r):
        self._add(r, getattr(self, "status", {}).get(r))

    def on_fail(self, r):
        self._add(r, None, r.failure)

    def summary(self, keep_types=("document", "xhr", "fetch")):
        """Keep doc/xhr/fetch in full, count static assets, always keep failures and >=400."""
        keep = [i for i in self.items if i[3] in keep_types or (i[2] or 0) >= 400 or len(i) > 5]
        other = {}
        for i in self.items:
            if i not in keep:
                other[i[3]] = other.get(i[3], 0) + 1
        return {"requests": keep, "assets": other, "total": len(self.items)}


async def timed(coro_fn, n=N):
    ts, out = [], None
    for _ in range(n):
        t = time.perf_counter()
        out = await coro_fn()
        ts.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(ts), 1), out


async def main():
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
        page = await ctx.new_page()
        net = NetLog(page)
        await page.goto("/user/login")
        await page.get_by_role("textbox", name="Username or Email Address").fill("demo")
        await page.get_by_role("textbox", name="Password").fill("demo-local-only")
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/")
        for path in PAGES:
            net.reset()
            if path != "/":
                await page.goto(path)
            else:
                await page.reload()
            await page.get_by_role("main").first.wait_for()
            await asyncio.sleep(0.5)
            r = {"doc_height": await page.evaluate("document.documentElement.scrollHeight")}
            shots = {
                "png_viewport": lambda: page.screenshot(),
                "png_full": lambda: page.screenshot(full_page=True),
                "jpeg70_viewport": lambda: page.screenshot(type="jpeg", quality=70),
                "jpeg70_full": lambda: page.screenshot(type="jpeg", quality=70, full_page=True),
                "jpeg70_viewport_anim_off_caret_hide": lambda: page.screenshot(type="jpeg", quality=70, animations="disabled", caret="hide"),
                "png_viewport_anim_off_caret_hide": lambda: page.screenshot(animations="disabled", caret="hide"),
            }
            for k, fn in shots.items():
                ms, data = await timed(fn)
                r[k] = {"ms": ms, "bytes": len(data)}
            ms, aria = await timed(lambda: page.get_by_role("main").first.aria_snapshot())
            r["aria_main"] = {"ms": ms, "bytes": len(aria.encode())}
            ms, aria_body = await timed(lambda: page.locator("body").aria_snapshot())
            r["aria_body"] = {"ms": ms, "bytes": len(aria_body.encode())}
            ms, _ = await timed(lambda: page.title())
            r["title"] = {"ms": ms}
            ms, _ = await timed(lambda: asyncio.sleep(0, page.url))
            r["url"] = {"ms": ms}
            t = time.perf_counter()
            try:
                await page.locator("main").aria_snapshot(timeout=2000)
                r["locator('main')"] = "ok"
            except Exception as e:
                r["locator('main')"] = f"{type(e).__name__} after {round((time.perf_counter() - t) * 1000)} ms"

            async def sequential():
                await page.screenshot(type="jpeg", quality=70, animations="disabled", caret="hide")
                await page.get_by_role("main").first.aria_snapshot()
                await page.title()
                return net.summary()

            async def parallel():
                _, _, _ = await asyncio.gather(
                    page.screenshot(type="jpeg", quality=70, animations="disabled", caret="hide"),
                    page.get_by_role("main").first.aria_snapshot(), page.title())
                return net.summary()

            ms, summ = await timed(sequential)
            r["step_capture_sequential_ms"] = ms
            ms, summ = await timed(parallel)
            r["step_capture_gather_ms"] = ms
            r["net_summary_bytes"] = len(json.dumps(summ, separators=(",", ":")))
            r["net_summary_total_requests"] = summ["total"]
            res[path] = r
            (__import__("pathlib").Path(__file__).parent / "out" / f"aria{path.replace('/', '_')}.yaml").write_text(aria, encoding="utf-8")
            (__import__("pathlib").Path(__file__).parent / "out" / f"net{path.replace('/', '_')}.json").write_text(json.dumps(summ, indent=1))
        # One real "step": click + navigation, then summary of what happened during it
        await page.goto("/")
        await page.get_by_role("main").first.wait_for()
        net.reset()
        await page.get_by_role("menu", name="Create…").click()
        await page.get_by_role("menuitem", name="New Repository").click()
        await page.wait_for_url("**/repo/create")
        await page.get_by_role("textbox", name="Repository Name").wait_for()
        res["step_net_summary_click_new_repo"] = net.summary()
        res["step_net_summary_bytes"] = len(json.dumps(net.summary(), separators=(",", ":")))
        await b.close()
    print(json.dumps(res, indent=1))


asyncio.run(main())
