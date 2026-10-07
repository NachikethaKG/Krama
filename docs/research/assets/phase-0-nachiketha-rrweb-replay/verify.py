# Replay the recording at several scales / DPRs with rrweb.Replayer and rrweb-player; check overlay alignment.
import json, pathlib, threading, http.server, functools
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).parent; WEB = ROOT / "web"; SHOTS = ROOT / "shots"; SHOTS.mkdir(exist_ok=True)
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
s = http.server.ThreadingHTTPServer(("127.0.0.1", 8766), functools.partial(Q, directory=str(WEB)))
threading.Thread(target=s.serve_forever, daemon=True).start()
results = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for dpr in (1, 2):
        for kind in ("raw", "player"):
            for scale in (1, 0.5, 0.37):
                pg = b.new_page(viewport={"width": 1400, "height": 950}, device_scale_factor=dpr)
                errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(f"http://127.0.0.1:8766/replay.html?kind={kind}&scale={scale}")
                pg.wait_for_function("window.__ready === true")
                for i in range(3):
                    r = pg.evaluate("i => window.__goStep(i)", i); r["pageErrors"] = errs[:]
                    results.append(r)
                    if dpr == 1: pg.screenshot(path=str(SHOTS / f"{kind}_s{scale}_step{i}.png"))
                    print(f"dpr={dpr} {kind:6} scale={scale:<5} step{i} scroll={r['replayScroll']} rec={r['recordedScroll']} eff={r['effScale']:.3f} border={r['iframeBorder']} errIn={r['errInside']:.3f} errOut={r['errOutside']:.3f} sandbox={r['sandbox']}")
                pg.close()
    b.close()
(ROOT / "results.json").write_text(json.dumps(results, indent=1))
print("max errInside", max(r["errInside"] for r in results), "max errOutside", max(r["errOutside"] for r in results))
