"""The API runs browsers in-process, so its event loop must be able to start subprocesses (Chromium)."""

import asyncio
import sys

import pytest

from app.dev_loop import factory
from app.main import check_event_loop


def test_dev_loop_can_start_a_subprocess() -> None:
    async def spawn() -> int:
        proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
        return await proc.wait()

    assert asyncio.run(spawn(), loop_factory=factory) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="the Selector loop only lacks subprocesses on Windows")
def test_startup_refuses_a_loop_that_cannot_start_the_browser() -> None:
    async def check() -> None:
        check_event_loop()

    loop = asyncio.SelectorEventLoop()
    try:
        with pytest.raises(RuntimeError, match=r"app\.dev_loop:factory"):
            loop.run_until_complete(check())
    finally:
        loop.close()
