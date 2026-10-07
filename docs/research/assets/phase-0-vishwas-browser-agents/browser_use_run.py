"""One browser-use run against local Gitea. Never prints the API key."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import psutil

os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["BROWSER_USE_CLOUD_SYNC"] = "false"
for line in Path(r"C:\Krama\backend\.env").read_text().splitlines():
    if line.startswith("GEMINI_API_KEY="):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip('"')

from google.genai import models as _genai_models  # noqa: E402

from browser_use import Agent, BrowserSession  # noqa: E402
from browser_use.llm.google.chat import ChatGoogle  # noqa: E402

# Count raw HTTP generate_content requests (browser-use retries inside ainvoke)
http = {"requests": 0, "statuses": [], "t": []}
_orig_gc = _genai_models.AsyncModels.generate_content
T0 = time.perf_counter()


async def _counting_gc(self, *a, **kw):
    http["requests"] += 1
    if http["requests"] > 15:
        raise RuntimeError("budget: more than 15 HTTP LLM requests")
    t = round(time.perf_counter() - T0, 1)
    try:
        r = await _orig_gc(self, *a, **kw)
        http["statuses"].append((t, 200))
        return r
    except Exception as e:
        http["statuses"].append((t, getattr(e, "code", type(e).__name__)))
        raise


_genai_models.AsyncModels.generate_content = _counting_gc

MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash"
calls = {"n": 0, "errors": []}
peak = {"rss_mb": 0.0}


class CountingGoogle(ChatGoogle):
    async def ainvoke(self, messages, output_format=None, **kw):  # type: ignore[override]
        calls["n"] += 1
        if calls["n"] > 15:
            raise RuntimeError("budget: more than 15 LLM calls")
        try:
            return await super().ainvoke(messages, output_format, **kw)
        except Exception as e:
            calls["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
            raise


async def sample_ram():
    me = psutil.Process()
    while True:
        total = 0
        for p in [me, *me.children(recursive=True)]:
            try:
                total += p.memory_info().rss
            except psutil.Error:
                pass
        peak["rss_mb"] = max(peak["rss_mb"], total / 2**20)
        await asyncio.sleep(0.5)


async def main():
    llm = CountingGoogle(model=MODEL, api_key=os.environ["GOOGLE_API_KEY"])
    session = BrowserSession(headless=True, viewport={"width": 1280, "height": 800})
    task = (
        "Go to http://localhost:3001/user/login and sign in with username 'demo' and password "
        "'demo-local-only'. Then create a new repository named 'bu-test-1' with 'Initialize Repository' "
        "checked. Done when the repository page /demo/bu-test-1 is shown."
    )
    agent = Agent(task=task, llm=llm, browser_session=session, max_failures=2)
    sampler = asyncio.create_task(sample_ram())
    t0 = time.perf_counter()
    err = None
    try:
        hist = await agent.run(max_steps=12)
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:300]}"
        hist = None
    wall = time.perf_counter() - t0
    sampler.cancel()
    out = {
        "model": MODEL,
        "wall_s": round(wall, 1),
        "llm_calls": calls["n"],
        "http_requests": http["requests"],
        "http_statuses_t_s": http["statuses"],
        "llm_errors": calls["errors"],
        "run_error": err,
        "peak_rss_mb_python_plus_children": round(peak["rss_mb"]),
    }
    if hist:
        out.update(
            steps=hist.number_of_steps(),
            is_done=hist.is_done(),
            is_successful=hist.is_successful(),
            final_result=(hist.final_result() or "")[:300],
            urls=hist.urls(),
            actions=[list(a.keys())[0] for a in hist.model_actions()],
            errors=[e for e in hist.errors() if e],
            tokens=getattr(hist, "usage", None) and hist.usage.model_dump(),
        )
    print(json.dumps(out, indent=2, default=str))


asyncio.run(main())
