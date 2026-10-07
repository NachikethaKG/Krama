"""A) Event loss around navigation: per-event binding calls vs JS batching (flush on timer/pagehide/beforeunload).

Fake site served by page.route. On page /a we burst DOM mutations and navigate away in the same task,
so the last events are emitted right before unload. Emitted count per document is persisted
synchronously in localStorage by the bootstrap; we compare it with what reached Python.
"""

import asyncio
import json

from playwright.async_api import async_playwright

from rr_inject import Sink, build_init_script

HTML = """<!doctype html><html><head><title>{t}</title></head><body><h1>{t}</h1>
<a id=next href="/{n}">next</a><div id=box></div>
<script>
window.burst = (k, nav) => {{
  const box = document.getElementById('box');
  for (let i = 0; i < k; i++) {{ const d = document.createElement('div'); d.textContent = 'row ' + i; box.appendChild(d);
    if (i % 50 === 0) setTimeout(() => box.appendChild(document.createElement('hr')), 0); }}
  if (nav) location.href = '/{n}';
}};
</script></body></html>"""


async def run(p, mode, how, rounds=5):
    sink = Sink()
    b = await p.chromium.launch()
    ctx = await b.new_context()
    await ctx.route("http://fake.test/**", lambda r: r.fulfill(
        content_type="text/html", body=HTML.format(t=r.request.url.rsplit("/", 1)[1] or "root",
                                                   n="p" + str(int(r.request.url.rsplit("/p", 1)[-1] or 0) + 1 if "/p" in r.request.url else "p1"))))
    await ctx.expose_binding("__krama_rr", sink.handler)
    await ctx.add_init_script(script=build_init_script(mode, {"recordAfter": "DOMContentLoaded"}, 500))
    page = await ctx.new_page()
    await page.goto("http://fake.test/p0")
    for i in range(rounds):
        await page.wait_for_function("window.__kramaRR")
        await asyncio.sleep(0.3)
        if how == "js-nav":           # mutations + location.href in the same task
            await page.evaluate("burst(400, true)")
            await page.wait_for_url(f"**/p{i + 1}")
        elif how == "pw-goto":         # mutations then immediate page.goto from Python
            await page.evaluate("burst(400, false)")
            await page.goto(f"http://fake.test/p{i + 1}")
        elif how == "pw-click-link":   # mutations queued then click a link right away
            await page.evaluate("setTimeout(() => burst(400, false), 0)")
            await page.click("#next")
            await page.wait_for_url(f"**/p{i + 1}")
    await asyncio.sleep(0.3)
    await page.evaluate("window.__kramaRR.flush()")
    await asyncio.sleep(0.5)
    counts = await page.evaluate(
        "Object.fromEntries(Object.keys(localStorage).filter(k=>k.startsWith('__rrcount:')).map(k=>[k.slice(10), +localStorage.getItem(k)]))")
    flushlog = await page.evaluate(
        "Object.keys(localStorage).filter(k=>k.startsWith('__rrflush:')).map(k=>localStorage.getItem(k))")
    await b.close()
    emitted = sum(counts.values())
    received = sum(len(d["events"]) for k, d in sink.docs.items() if k in counts)
    per_doc = [(d["path"], counts.get(k), len(d["events"])) for k, d in sorted(sink.docs.items(), key=lambda kv: kv[1]["order"]) if k in counts]
    return {"mode": mode, "how": how, "docs": len(counts), "emitted": emitted, "received": received, "lost": emitted - received,
            "binding_calls": sink.calls, "js_flush_log": flushlog[:3], "calls_by_reason": dict(sink.calls_by_reason), "per_doc(path,emitted,received)": per_doc}


async def main():
    out = []
    async with async_playwright() as p:
        for how in ["js-nav", "pw-goto", "pw-click-link"]:
            for mode in ["per", "batch", "hybrid"]:
                out.append(await run(p, mode, how))
    for r in out:
        print(json.dumps(r))


asyncio.run(main())
