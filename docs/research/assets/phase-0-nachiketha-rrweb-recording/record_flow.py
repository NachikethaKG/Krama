"""A) Record the Gitea create-repo flow (~60 s) with rrweb injected via add_init_script.

usage: python record_flow.py <mode per|batch> <mask none|default|all> <repo-name>
"""

from __future__ import annotations

import asyncio
import gzip
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

from playwright.async_api import async_playwright

from rr_inject import Sink, build_init_script

BASE = "http://localhost:3001"
PASSWORD = "demo-local-only"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

EV_TYPES = {0: "DomContentLoaded", 1: "Load", 2: "FullSnapshot", 3: "Incremental", 4: "Meta", 5: "Custom", 6: "Plugin"}
INC_SRC = {0: "Mutation", 1: "MouseMove", 2: "MouseInteraction", 3: "Scroll", 4: "ViewportResize", 5: "Input",
           6: "TouchMove", 7: "MediaInteraction", 8: "StyleSheetRule", 9: "CanvasMutation", 10: "Font", 11: "Log",
           12: "Drag", 13: "StyleDeclaration", 14: "Selection", 15: "AdoptedStyleSheet", 16: "CustomElement"}

MASKS = {
    "none": {"maskInputOptions": {"password": False}},   # explicitly turn rrweb's default password mask off
    "default": {},                                       # rrweb default = {password: true}
    "all": {"maskAllInputs": True},
}


async def wander(page, n=4, pause=1.5):
    vp = page.viewport_size
    for _ in range(n):
        await page.mouse.move(random.randint(50, vp["width"] - 50), random.randint(80, vp["height"] - 50), steps=25)
        await asyncio.sleep(pause)


async def main(mode: str, mask: str, repo: str) -> None:
    random.seed(7)
    opts = {"recordAfter": "DOMContentLoaded", "sampling": {"mousemove": 50, "scroll": 150, "input": "last"},
            "slimDOMOptions": "all", **MASKS[mask]}
    sink = Sink()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, base_url=BASE)
        await ctx.expose_binding("__krama_rr", sink.handler)
        await ctx.add_init_script(script=build_init_script(mode, opts))
        page = await ctx.new_page()
        marks = []
        t0 = time.perf_counter()

        def mark(name):
            marks.append((round(time.perf_counter() - t0, 2), name, page.url))

        await page.goto("/user/login"); mark("login page")
        await wander(page, 3)
        await page.get_by_role("textbox", name="Username or Email Address").fill("demo"); await asyncio.sleep(1.5)
        await page.get_by_role("textbox", name="Password").fill(PASSWORD); await asyncio.sleep(1.5)
        await page.get_by_role("button", name="Sign In").click()
        await page.wait_for_url(BASE + "/"); await page.get_by_role("main", name="Dashboard").wait_for(); mark("dashboard")
        await wander(page, 4)
        await page.mouse.wheel(0, 600); await asyncio.sleep(1.5); await page.mouse.wheel(0, -600); await asyncio.sleep(1.5)
        await page.get_by_role("menu", name="Create…").click(); await asyncio.sleep(1.5)
        await page.get_by_role("menuitem", name="New Repository").click()
        await page.wait_for_url("**/repo/create"); await page.get_by_role("textbox", name="Repository Name").wait_for(); mark("repo/create")
        await wander(page, 3)
        await page.get_by_role("textbox", name="Repository Name").press_sequentially(repo, delay=150); await asyncio.sleep(2)
        await page.get_by_role("checkbox", name="Initialize Repository").click(); await asyncio.sleep(2)
        await wander(page, 3)
        await page.get_by_role("button", name="Create Repository").click()
        await page.wait_for_url(f"**/demo/{repo}"); mark("repo page")
        await wander(page, 4)
        await page.mouse.wheel(0, 800); await asyncio.sleep(2)
        await page.evaluate("window.__kramaRR && window.__kramaRR.flush()")
        await asyncio.sleep(0.3)
        counts = await page.evaluate(
            "Object.fromEntries(Object.keys(localStorage).filter(k=>k.startsWith('__rrcount:')).map(k=>[k.slice(10), +localStorage.getItem(k)]))")
        await page.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('__rrcount:')).forEach(k=>localStorage.removeItem(k))")
        dur = time.perf_counter() - t0
        await ctx.close(); await browser.close()

    events = sink.all_events()
    blob = json.dumps(events, separators=(",", ":")).encode()
    gz = gzip.compress(blob, 6)
    by_type = Counter(EV_TYPES[e["type"]] for e in events)
    by_src = Counter(INC_SRC.get(e["data"].get("source"), "?") for e in events if e["type"] == 3)
    pages = []
    for doc_id, d in sorted(sink.docs.items(), key=lambda kv: kv[1]["order"]):
        evs = list(d["events"].values())
        b = json.dumps(evs, separators=(",", ":")).encode()
        fs = [len(json.dumps(e)) for e in evs if e["type"] == 2]
        pages.append({"path": d["path"], "received": len(evs), "emitted_in_page": counts.get(doc_id),
                      "lost": (counts.get(doc_id) or 0) - len(evs), "full_snapshots": len(fs), "meta": sum(e["type"] == 4 for e in evs),
                      "bytes": len(b), "fullsnapshot_bytes": fs, "gzip_bytes": len(gzip.compress(b, 6))})
    report = {
        "mode": mode, "mask": mask, "repo": repo, "duration_s": round(dur, 1), "marks": marks,
        "events": len(events), "by_type": by_type, "incremental_by_source": by_src,
        "json_bytes": len(blob), "gzip_bytes": len(gz), "binding_calls": sink.calls, "calls_by_reason": dict(sink.calls_by_reason),
        "password_in_json": PASSWORD in blob.decode(), "pages": pages,
        "docs_without_count": [k for k in counts if k not in sink.docs],
    }
    tag = f"{mode}-{mask}-{repo}"
    (OUT / f"events-{tag}.json").write_bytes(blob)
    (OUT / f"report-{tag}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:4]))
