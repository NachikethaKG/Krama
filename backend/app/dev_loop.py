"""uvicorn loop factory: `uvicorn app.main:app --reload --loop app.dev_loop:factory`.

uvicorn uses the Selector loop on Windows when --reload or --workers is on, and the Selector loop can't start
subprocesses, so Playwright can't launch Chromium inside the API. This always gives the Proactor loop on
Windows (docs/research/phase-1-vishwas-database.md). Other platforms get the default loop.
"""

import asyncio
import sys


def factory() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()
