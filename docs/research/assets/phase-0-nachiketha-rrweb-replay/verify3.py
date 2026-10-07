# Which redraw trigger keeps the overlay aligned DURING playback (rrweb replays scroll with behavior:'smooth')?
import json, pathlib, threading, http.server, functools
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).parent; WEB = ROOT / "web"
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
s = http.server.ThreadingHTTPServer(("127.0.0.1", 8769), functools.partial(Q, directory=str(WEB)))
threading.Thread(target=s.serve_forever, daemon=True).start()
out = []
# sample alignment every 30ms during playback through the smooth scroll
SAMPLE = """async () => { current = steps[2]; replayer.pause(steps[1].timeOffset); await new Promise(r=>setTimeout(r,100)); redraw();
  const samples = []; replayer.play(steps[1].timeOffset); const t0 = performance.now();
  while (performance.now() - t0 < 1700) { await new Promise(r=>setTimeout(r,30)); const m = __measure(); samples.push([Math.round(m.t), m.scroll[1], +m.errInside.toFixed(2)]); }
  return {samples, scrollFires: window.__scrollFires}; }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for kind in ("raw", "player"):
        for sync in ("cast", "scroll", "raf"):
            pg = b.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: print("ERR", e))
            pg.goto(f"http://127.0.0.1:8769/replay.html?kind={kind}&scale=0.5&sync={sync}"); pg.wait_for_function("window.__ready === true")
            r = pg.evaluate(SAMPLE); sm = r["samples"]
            moving = [x for x in sm if 1300 < x[1] < 1824]
            print(f"{kind:6} sync={sync:6} scrollFires={r['scrollFires']:3} maxErr={max(x[2] for x in sm):7.2f} maxErrWhileMoving={max([x[2] for x in moving] or [0]):7.2f} final={sm[-1]}")
            out.append({"kind": kind, "sync": sync, **r}); pg.close()
    b.close()
(ROOT / "results_playback.json").write_text(json.dumps(out, indent=1))
