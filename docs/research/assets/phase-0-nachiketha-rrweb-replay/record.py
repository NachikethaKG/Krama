# Record a small rrweb session in headless Chromium and save events + ground-truth step bboxes.
import json, pathlib, threading, http.server, functools, sys
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).parent
WEB = ROOT / "web"
def serve():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 8765), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
srv = serve()
BBOX_JS = """sel => { const r = document.querySelector(sel).getBoundingClientRect();
  return {t: Date.now(), bbox: [r.x + scrollX, r.y + scrollY, r.width, r.height], scroll: [scrollX, scrollY]}; }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800})
    pg.goto("http://127.0.0.1:8765/site.html")
    pg.add_script_tag(path=str(WEB / "vendor" / "rrweb.umd.js"))
    pg.evaluate("() => { window.__ev = []; window.__stop = rrweb.record({emit: e => window.__ev.push(e)}); }")
    pg.wait_for_timeout(500)
    steps = []
    s = pg.evaluate(BBOX_JS, "#title"); s["name"] = "title (no scroll)"; steps.append(s)
    pg.mouse.move(100, 50); pg.wait_for_timeout(300)
    pg.mouse.wheel(0, 1300); pg.wait_for_timeout(600)   # scrollY -> 1300
    s = pg.evaluate(BBOX_JS, "#second"); s["name"] = "second (scrollY~1300)"; steps.append(s)
    pg.click("#second"); pg.wait_for_timeout(400)
    pg.locator("#target").scroll_into_view_if_needed(); pg.wait_for_timeout(600)
    s = pg.evaluate(BBOX_JS, "#target"); s["name"] = "target (scrolled)"; steps.append(s)
    pg.click("#target"); pg.wait_for_timeout(800)
    ev = pg.evaluate("() => { window.__stop(); return window.__ev; }")
    t0 = ev[0]["timestamp"]
    for s in steps: s["timeOffset"] = s["t"] - t0
    (WEB / "events.json").write_text(json.dumps(ev))
    (WEB / "steps.json").write_text(json.dumps(steps, indent=1))
    print(len(ev), "events;", json.dumps(steps, indent=1))
    b.close()
srv.shutdown()
