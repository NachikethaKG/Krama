# Dynamic checks: play across a scroll (event-cast redraw) and live container rescale.
import json, pathlib, threading, http.server, functools
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).parent; WEB = ROOT / "web"
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
s = http.server.ThreadingHTTPServer(("127.0.0.1", 8768), functools.partial(Q, directory=str(WEB)))
threading.Thread(target=s.serve_forever, daemon=True).start()
out = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for kind in ("raw", "player"):
        pg = b.new_page(viewport={"width": 1400, "height": 950})
        pg.on("pageerror", lambda e: print("ERR", e))
        pg.goto(f"http://127.0.0.1:8768/replay.html?kind={kind}&scale=0.5"); pg.wait_for_function("window.__ready === true")
        r = pg.evaluate("() => __playTest()"); print(kind, "play:", r); out.append({"kind": kind, "play": r})
        pg.evaluate("() => __goStep(2)")
        r = pg.evaluate("() => __rescaleTest(0.75)"); print(kind, "rescale(no redraw):", r); out.append({"kind": kind, "rescale": r})
        pg.screenshot(path=str(ROOT / "shots" / f"{kind}_rescaled_0.75.png"))
        pg.close()
    b.close()
(ROOT / "results_dynamic.json").write_text(json.dumps(out, indent=1))
