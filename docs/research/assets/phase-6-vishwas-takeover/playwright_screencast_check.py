"""Second check for #131: Playwright's own `page.screencast` (new in recent Playwright; 1.63 here) instead of raw CDP.

    cd backend && uv run python <path>/playwright_screencast_check.py --out <dir>

Checks: frames on an idle page, fps and size on an animating page, the frame size it picks, and whether an async
on_frame callback that is slow (a slow viewer) slows the stream down (Playwright acks a frame only after the
callback finishes), i.e. whether we get backpressure for free.
"""

import argparse
import asyncio
import io
import json
import statistics
import time
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.async_api import async_playwright

PAGE = """<!doctype html><style>#s{width:60px;height:60px;background:#36c;margin:40px}
body.anim #s{animation:r 1s linear infinite}@keyframes r{to{transform:rotate(360deg)}}</style>
<h1>Takeover spike</h1><div id=s></div><input id=name>"""


async def main(out: Path) -> None:
    res: dict[str, Any] = {}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await (await browser.new_context(viewport={"width": 1280, "height": 800})).new_page()
            await page.set_content(PAGE)
            frames: list[tuple[float, int]] = []
            last: dict[str, Any] = {}
            delay = {"s": 0.0}

            async def on_frame(f: Any) -> None:
                frames.append((time.perf_counter(), len(f["data"])))
                last.update(f)
                if delay["s"]:
                    await asyncio.sleep(delay["s"])  # a slow viewer

            async def window(seconds: float) -> dict[str, Any]:
                t0 = time.perf_counter()
                await asyncio.sleep(seconds)
                got = [f for f in frames if f[0] >= t0]
                return {
                    "fps": round(len(got) / seconds, 1),
                    "kb_avg": round(statistics.mean(s for _, s in got) / 1024, 1) if got else None,
                }

            await page.screencast.start(on_frame=on_frame, quality=60, size={"width": 1280, "height": 800})
            await asyncio.sleep(1)
            res["idle_page"] = await window(3)
            await page.evaluate("document.body.classList.add('anim')")
            res["animating"] = await window(4)
            res["frame_size"] = Image.open(io.BytesIO(last["data"])).size
            res["viewport_in_frame_info"] = [last["viewportWidth"], last["viewportHeight"]]
            delay["s"] = 0.1
            res["animating_slow_viewer_100ms"] = await window(4)
            delay["s"] = 0.0
            await page.screencast.stop()

            frames.clear()
            await page.screencast.start(on_frame=on_frame, quality=60)  # no size: Playwright's default
            await asyncio.sleep(1)
            res["default_size_frame"] = Image.open(io.BytesIO(last["data"])).size
            await page.screencast.stop()
        finally:
            await browser.close()
    (out / "results-playwright-screencast.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).parent)
    asyncio.run(main(ap.parse_args().out))
