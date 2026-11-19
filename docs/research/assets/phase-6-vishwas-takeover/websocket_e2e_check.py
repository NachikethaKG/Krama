"""Third check for #131: the whole loop over a FastAPI WebSocket, like the web UI would use it.

    cd backend && uv run python <path>/websocket_e2e_check.py --out <dir>

- A tiny FastAPI app on localhost:8765 (stands in for the backend) owns a headless "run" browser at 1280x800 and
  streams its screencast as binary JPEG WebSocket messages; it applies input messages (JSON) with page.mouse /
  page.keyboard.
- A viewer page on localhost:8766 (stands in for the Next.js frontend: another port = another origin, same site)
  is opened in a second browser. It gets the session cookie from :8765 first, then opens the WebSocket.
- Checks: is the SameSite=Lax HttpOnly cookie sent on the cross-port WebSocket handshake? Which Origin arrives?
  Is a socket from a foreign origin refused? Then: viewer key press -> frame showing it back in the viewer
  (round trip through server, run browser, screencast, WebSocket, <img>), and a click typed into the run page.
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from playwright.async_api import Page, async_playwright

ALLOWED_ORIGINS = {"http://localhost:8766"}
TARGET = """<!doctype html><style>body{font:18px system-ui;margin:40px}input{font-size:18px;width:400px}</style>
<h1>Run page</h1><input id=q autocomplete=off><p id=log></p>"""

VIEWER = """<!doctype html><body style="margin:0"><img id=v style="width:1280px;height:800px;display:block">
<script>
window.stats = {frames: 0, bytes: 0, lat: [], closed: null};
let pending = null;
const img = document.getElementById('v');
const ws = new WebSocket('ws://localhost:8765/runs/r1/takeover/ws');
ws.binaryType = 'blob';
ws.onclose = (e) => { window.stats.closed = e.code; };
ws.onmessage = (e) => {
  if (typeof e.data === 'string') { window.hello = JSON.parse(e.data); return; }
  window.stats.frames++; window.stats.bytes += e.data.size;
  const url = URL.createObjectURL(e.data);
  img.onload = () => { URL.revokeObjectURL(url); if (pending !== null) { window.stats.lat.push(performance.now() - pending); pending = null; } };
  img.src = url;
};
// The viewer turns its own events into input messages, in page (CSS px) coordinates of the run browser.
img.addEventListener('mousedown', (e) => ws.send(JSON.stringify({t: 'click', x: e.offsetX, y: e.offsetY})));
window.sendKey = (k) => { pending = performance.now(); ws.send(JSON.stringify({t: 'key', key: k})); };
</script></body>"""


def build_app(run_page: Page, seen: dict[str, Any]) -> FastAPI:
    app = FastAPI()

    @app.get("/login")
    async def login(response: Response) -> dict[str, str]:
        response.set_cookie("krama_session", "test-session", httponly=True, samesite="lax")
        return {"ok": "yes"}

    @app.websocket("/runs/{run_id}/takeover/ws")
    async def takeover(ws: WebSocket, run_id: str) -> None:
        origin = ws.headers.get("origin")
        cookie = ws.cookies.get("krama_session")
        seen.setdefault("handshakes", []).append({"origin": origin, "cookie_sent": cookie is not None})
        # CORS does not cover WebSockets: the server must check Origin itself (cross-site WebSocket hijacking).
        if origin not in ALLOWED_ORIGINS or cookie != "test-session":
            await ws.close(code=4403)  # closing before accept → the browser sees a failed handshake (1006)
            return
        await ws.accept()
        await ws.send_text(json.dumps({"run_id": run_id}))

        async def on_frame(f: Any) -> None:
            await ws.send_bytes(f["data"])  # Playwright acks after this returns: a slow socket slows the stream

        await run_page.screencast.start(on_frame=on_frame, quality=60, size={"width": 1280, "height": 800})
        try:
            while True:
                msg = json.loads(await ws.receive_text())
                if msg["t"] == "click":
                    await run_page.mouse.click(float(msg["x"]), float(msg["y"]))
                elif msg["t"] == "key":
                    await run_page.keyboard.press(str(msg["key"]))
        except WebSocketDisconnect:
            pass
        finally:
            await run_page.screencast.stop()

    return app


async def main(out: Path) -> None:
    res: dict[str, Any] = {}
    seen: dict[str, Any] = {}
    async with async_playwright() as pw:
        run_browser = await pw.chromium.launch(headless=True)
        viewer_browser = await pw.chromium.launch(headless=True)
        servers: list[uvicorn.Server] = []
        tasks: list[asyncio.Task[Any]] = []
        try:
            run_page = await (await run_browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
            await run_page.set_content(TARGET)
            await run_page.evaluate(
                "document.addEventListener('keydown', e => document.getElementById('log').textContent += e.key)"
            )
            viewer_app = FastAPI()
            viewer_app.get("/")(lambda: HTMLResponse(VIEWER))
            for app, port in ((build_app(run_page, seen), 8765), (viewer_app, 8766), (viewer_app, 8767)):
                server = uvicorn.Server(uvicorn.Config(app, host="localhost", port=port, log_level="warning"))
                servers.append(server)
                tasks.append(asyncio.create_task(server.serve()))
            await asyncio.sleep(1.5)

            # A foreign origin, with the cookie: must be refused.
            ctx = await viewer_browser.new_context(viewport={"width": 1300, "height": 820})
            evil = await ctx.new_page()
            await evil.goto("http://localhost:8765/login")  # sets the cookie for host localhost
            await evil.goto("http://localhost:8767/")  # another origin, SAME site (any localhost port)
            await asyncio.sleep(1.5)
            res["foreign_origin_same_site"] = {"server_saw": seen.get("handshakes", [])[-1:], "client": await evil.evaluate("window.stats")}
            await evil.goto("http://127.0.0.1:8766/")  # another origin and another site
            await asyncio.sleep(1.5)
            res["foreign_origin_cross_site"] = {"server_saw": seen.get("handshakes", [])[-1:], "client": await evil.evaluate("window.stats")}
            await evil.close()

            # The real viewer.
            viewer = await ctx.new_page()
            await viewer.goto("http://localhost:8766/")
            await viewer.wait_for_function("window.hello && window.stats.frames > 0", timeout=10_000)
            res["viewer_handshake_server_saw"] = seen["handshakes"][-1]
            res["first_frames"] = await viewer.evaluate("window.stats.frames")

            # Click into the run page's input through the viewer's <img>, then type.
            box = await run_page.locator("#q").bounding_box()
            assert box
            await viewer.mouse.click(box["x"] + 20, box["y"] + box["height"] / 2)
            await asyncio.sleep(0.3)
            await run_page.evaluate("document.getElementById('q').style.caretColor = 'transparent'")
            for i in range(30):
                await viewer.evaluate(f"window.sendKey('{'abcdefghij'[i % 10]}')")
                await asyncio.sleep(0.3)
            stats = await viewer.evaluate("window.stats")
            lat = sorted(stats["lat"])
            res["round_trip_key_to_displayed_frame_ms"] = {
                "n": len(lat),
                "p50": round(statistics.median(lat), 1),
                "p95": round(lat[int(0.95 * (len(lat) - 1))], 1),
                "max": round(lat[-1], 1),
            }
            res["run_page_input_value"] = await run_page.input_value("#q")
            res["frames_total"] = stats["frames"]
            res["kb_total"] = round(stats["bytes"] / 1024)
            await viewer.close()
            await asyncio.sleep(0.5)
        finally:
            for s in servers:
                s.should_exit = True
            await asyncio.gather(*tasks, return_exceptions=True)
            await viewer_browser.close()
            await run_browser.close()
    (out / "results-websocket-e2e.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent)
    asyncio.run(main(ap.parse_args().out))
