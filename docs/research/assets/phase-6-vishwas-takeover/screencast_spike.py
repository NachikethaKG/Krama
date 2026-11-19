"""Spike for #131 (human takeover): CDP screencast + input on a headless Chromium, as Krama's runs open it.

Run from the backend folder (psutil is not a backend dependency, so it is added for this run only):

    cd backend && uv run --with psutil python <path>/screencast_spike.py --out <dir>

What it measures, on a local page with a form (no network):
  1. idle: does the screencast send frames when nothing changes? (page idle, then a focused input with a caret)
  2. no-ack: what happens when frames are not acknowledged with Page.screencastFrameAck
  3. settings: fps, frame size, CPU and RAM per (quality, maxWidth, everyNthFrame) while a CSS animation runs
  4. input: a click and typed text through raw CDP Input.* and through Playwright's page.mouse / page.keyboard;
     checks the DOM got them (special keys, insertText for paste, Ctrl+A)
  5. latency: key press -> next frame, on a page where only the key changes pixels
  6. a 15 s "human takeover" session: typing every 150 ms while the animation runs, CPU and RAM sampled
Nothing is written but the JSON results and one sample frame.
"""

import argparse
import asyncio
import base64
import io
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

import psutil
from PIL import Image
from playwright.async_api import CDPSession, Page, async_playwright

PAGE = """<!doctype html><html><head><title>Takeover spike</title><style>
body { font: 16px system-ui; margin: 40px; }
#spin { width: 60px; height: 60px; background: #36c; display: none; }
body.anim #spin { display: block; animation: r 1s linear infinite; }
@keyframes r { to { transform: rotate(360deg); } }
input, textarea { font-size: 18px; padding: 6px; width: 400px; display: block; margin: 8px 0; }
body.nocaret input, body.nocaret textarea { caret-color: transparent; }
</style></head><body>
<h1>Sign in to continue</h1>
<div id="spin"></div>
<label>Name <input id="name" autocomplete="off"></label>
<label>Password <input id="pw" type="password" autocomplete="off"></label>
<label>Notes <textarea id="notes" rows="3"></textarea></label>
<button id="go" onclick="document.getElementById('clicks').textContent = +document.getElementById('clicks').textContent + 1">Continue</button>
<p>Clicks: <span id="clicks">0</span></p>
<p id="keys"></p>
<script>
document.addEventListener('keydown', e => { document.getElementById('keys').textContent += '[' + e.key + ']'; });
</script>
</body></html>"""


BUSY = "<!doctype html><html><body style='font:14px system-ui;margin:0'>" + "".join(
    f"<div style='display:flex;gap:12px;padding:6px 16px;border-bottom:1px solid #ddd;background:{c}'>"
    f"<b style='color:#0969da'>issue #{i} fix the label colour in settings</b><span>opened {i} days ago by user{i}</span>"
    f"<span style='background:#d73a4a;color:#fff;border-radius:8px;padding:0 6px'>bug</span></div>"
    for i, c in zip(range(120), ["#fff", "#f6f8fa"] * 60)
) + "</body></html>"


class Screencast:
    """Collects screencast frames from one CDP session."""

    def __init__(self, cdp: CDPSession, *, ack: bool = True) -> None:
        self.cdp, self.ack = cdp, ack
        self.frames: list[tuple[float, int, dict[str, Any]]] = []  # (arrival perf_counter, jpeg bytes, metadata)
        self.last_jpeg = b""
        self.event = asyncio.Event()
        cdp.on("Page.screencastFrame", self._on_frame)

    def _on_frame(self, params: dict[str, Any]) -> None:
        jpeg = base64.b64decode(params["data"])
        self.frames.append((time.perf_counter(), len(jpeg), params["metadata"]))
        self.last_jpeg = jpeg
        self.event.set()
        if self.ack:
            asyncio.ensure_future(self.cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]}))

    async def start(self, **opts: Any) -> None:
        self.frames.clear()
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", **opts})

    async def stop(self) -> None:
        await self.cdp.send("Page.stopScreencast")

    def count_since(self, t: float) -> int:
        return sum(1 for f in self.frames if f[0] >= t)


def browser_procs() -> list[psutil.Process]:
    """Chromium processes started by this script (python -> playwright driver (node) -> chrome*)."""
    out = []
    for p in psutil.Process(os.getpid()).children(recursive=True):
        try:
            if "chrom" in p.name().lower() or "headless" in p.name().lower():
                out.append(p)
        except psutil.NoSuchProcess:
            pass
    return out


def cpu_seconds(procs: list[psutil.Process]) -> float:
    total = 0.0
    for p in procs:
        try:
            t = p.cpu_times()
            total += t.user + t.system
        except psutil.NoSuchProcess:
            pass
    return total


def memory_mb(procs: list[psutil.Process]) -> dict[str, float]:
    rss = private = 0
    for p in procs:
        try:
            m = p.memory_info()
            rss += m.rss
            private += getattr(m, "private", 0)
        except psutil.NoSuchProcess:
            pass
    return {"rss_mb": round(rss / 2**20), "private_mb": round(private / 2**20)}


async def measure(seconds: float, sc: Screencast | None, work=None) -> dict[str, Any]:
    """CPU (% of one core) of the browser and of this python process, frames, sizes, over `seconds`."""
    procs = browser_procs()
    me = psutil.Process()
    c0, m0, t0 = cpu_seconds(procs), sum(me.cpu_times()[:2]), time.perf_counter()
    psutil.cpu_percent(None)  # primes the whole-machine counter
    peak = memory_mb(procs)
    task = asyncio.create_task(work()) if work else None
    end = t0 + seconds
    while time.perf_counter() < end:
        await asyncio.sleep(0.5)
        now = memory_mb(browser_procs())
        if now["rss_mb"] > peak["rss_mb"]:
            peak = now
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    wall = time.perf_counter() - t0
    out: dict[str, Any] = {
        "seconds": round(wall, 1),
        "browser_cpu_pct_of_one_core": round(100 * (cpu_seconds(browser_procs()) - c0) / wall, 1),
        "python_cpu_pct_of_one_core": round(100 * (sum(me.cpu_times()[:2]) - m0) / wall, 1),
        "machine_cpu_pct_all_cores": psutil.cpu_percent(None),  # how busy the laptop was (all 16 threads)
        "browser_processes": len(procs),
        "browser_mem_peak": peak,
    }
    if sc is not None:
        frames = [f for f in sc.frames if f[0] >= t0]
        sizes = [f[1] for f in frames]
        out.update(
            frames=len(frames),
            fps=round(len(frames) / wall, 1),
            frame_kb_avg=round(statistics.mean(sizes) / 1024, 1) if sizes else None,
            frame_kb_max=round(max(sizes) / 1024, 1) if sizes else None,
            kbit_per_s=round(sum(sizes) * 8 / 1024 / wall),
        )
    return out


async def bbox_center(page: Page, sel: str) -> tuple[float, float]:
    b = await page.locator(sel).bounding_box()
    assert b is not None
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


async def cdp_click(cdp: CDPSession, x: float, y: float) -> None:
    for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
        params: dict[str, Any] = {"type": kind, "x": x, "y": y}
        if kind != "mouseMoved":
            params.update(button="left", clickCount=1)
        await cdp.send("Input.dispatchMouseEvent", params)


async def cdp_key(cdp: CDPSession, key: str, code: str, vk: int, text: str | None = None, modifiers: int = 0) -> None:
    down: dict[str, Any] = {"type": "keyDown", "key": key, "code": code, "windowsVirtualKeyCode": vk, "modifiers": modifiers}
    if text:
        down["text"] = text
    await cdp.send("Input.dispatchKeyEvent", down)
    await cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "code": code, "windowsVirtualKeyCode": vk, "modifiers": modifiers})


async def cdp_type(cdp: CDPSession, s: str) -> None:
    for ch in s:
        await cdp_key(cdp, ch, f"Key{ch.upper()}" if ch.isalpha() else "", ord(ch.upper()), text=ch)


async def main(out_dir: Path) -> None:
    results: dict[str, Any] = {"cpu": "see note", "logical_cpus": psutil.cpu_count()}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)  # what PlaywrightSession does (headless shell)
        try:
            results["browser_version"] = browser.version
            context = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
            page = await context.new_page()
            await page.set_content(PAGE)
            cdp = await context.new_cdp_session(page)
            await asyncio.sleep(1)

            # Baseline: no screencast, idle and animating.
            results["baseline_idle_no_screencast"] = await measure(5, None)
            await page.evaluate("document.body.classList.add('anim')")
            results["baseline_anim_no_screencast"] = await measure(5, None)
            await page.evaluate("document.body.classList.remove('anim')")

            # 1. Idle: frames only on change?
            sc = Screencast(cdp)
            await sc.start(quality=70, maxWidth=1280, maxHeight=800)
            await asyncio.sleep(1.0)
            t = time.perf_counter()
            await asyncio.sleep(4)
            idle_frames = sc.count_since(t)
            await page.focus("#name")  # caret blinks in a focused input
            await asyncio.sleep(0.5)
            t = time.perf_counter()
            await asyncio.sleep(4)
            caret_frames = sc.count_since(t)
            await page.evaluate("document.activeElement.blur()")
            await sc.stop()
            results["idle"] = {
                "frames_in_4s_idle_page": idle_frames,
                "frames_in_4s_with_blinking_caret": caret_frames,
            }
            first = Image.open(io.BytesIO(sc.last_jpeg))
            results["frame_example"] = {"size": first.size, "metadata": sc.frames[-1][2] if sc.frames else None}

            # 2. No ack: does the stream stall?
            cdp.remove_listener("Page.screencastFrame", sc._on_frame)  # only the non-acking listener now
            noack = Screencast(cdp, ack=False)
            await page.evaluate("document.body.classList.add('anim')")
            await noack.start(quality=70, maxWidth=1280, maxHeight=800)
            await asyncio.sleep(3)
            results["no_ack_frames_in_3s_animating"] = len(noack.frames)
            await noack.stop()
            cdp.remove_listener("Page.screencastFrame", noack._on_frame)
            cdp.on("Page.screencastFrame", sc._on_frame)
            await asyncio.sleep(0.5)

            # 3. Settings while the animation runs.
            settings = [
                {"quality": 80, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 1},
                {"quality": 60, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 1},
                {"quality": 40, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 1},
                {"quality": 60, "maxWidth": 960, "maxHeight": 600, "everyNthFrame": 1},
                {"quality": 60, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 2},
                {"quality": 60, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 4},
            ]
            results["settings_animating"] = []
            for opts in settings * 2:  # two rounds: CPU numbers on a laptop are noisy
                await sc.start(**opts)
                await asyncio.sleep(0.5)
                m = await measure(5, sc)
                await sc.stop()
                await asyncio.sleep(0.3)
                results["settings_animating"].append({"opts": opts, **m})
            await page.evaluate("document.body.classList.remove('anim')")

            # 4. Input through raw CDP.
            await sc.start(quality=60, maxWidth=1280, maxHeight=800)
            x, y = await bbox_center(page, "#name")
            await cdp_click(cdp, x, y)
            await cdp_type(cdp, "alice")
            await cdp_key(cdp, "Backspace", "Backspace", 8)
            await cdp.send("Input.insertText", {"text": " pasted ✓ é"})  # what a clipboard paste would send
            x, y = await bbox_center(page, "#pw")
            await cdp_click(cdp, x, y)
            await cdp_type(cdp, "secret")
            await cdp_key(cdp, "Tab", "Tab", 9)  # focus moves to the textarea
            await cdp_type(cdp, "ab")
            await cdp_key(cdp, "a", "KeyA", 65, modifiers=2)  # Ctrl+A selects all in the textarea
            await cdp.send("Input.insertText", {"text": "replaced"})
            await cdp_key(cdp, "Enter", "Enter", 13, text="\r")
            x, y = await bbox_center(page, "#go")
            await cdp_click(cdp, x, y)
            await asyncio.sleep(0.3)
            dom = await page.evaluate(
                "(() => { const $ = (i) => document.getElementById(i); return {name: $('name').value, pw_len: $('pw').value.length,"
                " notes: $('notes').value, clicks: $('clicks').textContent, keys: $('keys').textContent,"
                " active: document.activeElement.id}; })()"
            )
            results["cdp_input_dom"] = dom
            (out_dir / "sample-frame.jpg").write_bytes(sc.last_jpeg)  # the form, password shown as dots

            # Same through Playwright's own mouse/keyboard (which use CDP Input underneath).
            await page.fill("#name", "")
            x, y = await bbox_center(page, "#name")
            await page.mouse.click(x, y)
            await page.keyboard.type("bob")
            await page.keyboard.press("Shift+Home")
            await page.keyboard.insert_text("carol")
            await page.mouse.click(*(await bbox_center(page, "#go")))
            results["playwright_input_dom"] = await page.evaluate("({name: document.getElementById('name').value, clicks: document.getElementById('clicks').textContent})")

            # 5. Latency: key press -> next frame. Caret hidden so only the typed letter changes pixels.
            await page.evaluate("document.body.classList.add('nocaret'); document.getElementById('keys').textContent=''")
            await page.fill("#notes", "")
            await page.focus("#notes")
            await asyncio.sleep(0.5)
            lat_cdp, lat_pw = [], []
            for i in range(40):
                sc.event.clear()
                n = len(sc.frames)
                t = time.perf_counter()
                if i % 2 == 0:
                    await cdp_key(cdp, "x", "KeyX", 88, text="x")
                else:
                    await page.keyboard.press("y")
                try:
                    await asyncio.wait_for(sc.event.wait(), 2)
                    while len(sc.frames) <= n:
                        sc.event.clear()
                        await asyncio.wait_for(sc.event.wait(), 2)
                    (lat_cdp if i % 2 == 0 else lat_pw).append((sc.frames[n][0] - t) * 1000)
                except TimeoutError:
                    pass
                await asyncio.sleep(0.25)
            await sc.stop()

            def summary(xs: list[float]) -> dict[str, Any]:
                xs = sorted(xs)
                return {
                    "n": len(xs),
                    "p50_ms": round(statistics.median(xs), 1),
                    "p95_ms": round(xs[int(0.95 * (len(xs) - 1))], 1),
                    "max_ms": round(xs[-1], 1),
                }

            results["latency_key_to_frame"] = {"raw_cdp": summary(lat_cdp), "playwright_keyboard": summary(lat_pw)}

            # 6. 15 s takeover session: animation + typing every 150 ms, default settings.
            await page.evaluate("document.body.classList.remove('nocaret'); document.body.classList.add('anim')")
            await page.fill("#notes", "")
            await page.focus("#notes")

            async def typing() -> None:
                while True:
                    await page.keyboard.type("k")
                    await asyncio.sleep(0.15)

            await page.evaluate("document.getElementById('keys').textContent=''")
            results["session_15s_typing_animating_no_screencast"] = await measure(15, None, typing)
            await page.fill("#notes", "")
            await page.evaluate("document.getElementById('keys').textContent=''")
            await sc.start(quality=60, maxWidth=1280, maxHeight=800)
            results["session_15s_typing_animating_q60"] = await measure(15, sc, typing)
            await sc.stop()
            await page.evaluate("document.body.classList.remove('anim')")
            await page.fill("#notes", "")
            await page.evaluate("document.getElementById('keys').textContent=''")
            await page.focus("#notes")
            await sc.start(quality=60, maxWidth=1280, maxHeight=800)
            results["session_15s_typing_static_page_q60"] = await measure(15, sc, typing)
            await sc.stop()

            # 7. A text-heavy page (a stand-in for a real site): size of one full frame per quality.
            await page.set_content(BUSY)
            results["busy_page_frame_kb"] = {}
            for q in (40, 60, 80):
                await sc.start(quality=q, maxWidth=1280, maxHeight=800)
                await asyncio.sleep(0.3)
                await page.mouse.wheel(0, 200)  # a change, so a fresh frame is sent
                await asyncio.sleep(0.5)
                await sc.stop()
                results["busy_page_frame_kb"][f"q{q}"] = round(len(sc.last_jpeg) / 1024, 1)
            (out_dir / "sample-frame-busy.jpg").write_bytes(sc.last_jpeg)
        finally:
            await browser.close()
    left = browser_procs()
    results["browser_processes_left_after_close"] = len(left)
    (out_dir / "results-screencast.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent)
    asyncio.run(main(ap.parse_args().out))
