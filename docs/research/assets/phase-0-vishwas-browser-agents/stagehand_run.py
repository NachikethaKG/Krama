"""Stagehand live run on local Gitea: login (no LLM), observe + 2x act. Never prints the API key."""

import asyncio
import glob
import json
import os
import time
from pathlib import Path

for line in Path(r"C:\Krama\backend\.env").read_text().splitlines():
    if line.startswith("GEMINI_API_KEY="):
        KEY = line.split("=", 1)[1].strip().strip('"')
        os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"] = os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = KEY

from stagehand import Stagehand, local_browser  # noqa: E402

EXE = sorted(glob.glob(os.path.expanduser(r"~\AppData\Local\ms-playwright\chromium-*\chrome-win*\chrome.exe")))[-1]
BASE = "http://localhost:3001"
out: dict = {}


def dump(r):
    try:
        return json.loads(r.model_dump_json(by_alias=True))
    except Exception:
        return repr(r)[:1500]


async def timed(name, coro):
    t0 = time.perf_counter()
    try:
        r = await coro
        out[name] = {"s": round(time.perf_counter() - t0, 1), "result": dump(r)}
        return r
    except Exception as e:
        out[name] = {"s": round(time.perf_counter() - t0, 1), "error": f"{type(e).__name__}: {str(e)[:500]}"}
        return None


async def main():
    b = await local_browser.launch(headless=True, executable_path=EXE, viewport_width=1280, viewport_height=800)
    try:
        sh = await Stagehand.create(browser=b, model="google/gemini-2.5-flash", model_api_key=KEY, cache=True, self_heal=True)
        page = await b.context.new_page(f"{BASE}/user/login")
        await page.locator("#user_name").fill("demo")
        await page.locator("#password").fill("demo-local-only")
        await page.locator("form.ui.form button.primary").click()
        await asyncio.sleep(2)
        await page.goto(f"{BASE}/repo/create")
        out["url_before"] = page.url if isinstance(page.url, str) else await page.url()
        await timed("observe", sh.observe("the repository name field", page=page))
        await timed("act_type", sh.act("type sh-test-1 into the repository name field", page=page))
        await timed("act_click", sh.act("click Create Repository", page=page))
        await asyncio.sleep(2)
        out["url_after"] = page.url if isinstance(page.url, str) else await page.url()
        await timed("metrics", sh.metrics())
    finally:
        await b.close()
    print(json.dumps(out, indent=2, default=str))


asyncio.run(main())
