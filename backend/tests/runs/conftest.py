import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

import pytest

from app.runs import InProcessExecutor


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def stop_runs(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Shut down every `InProcessExecutor` the test made, even when it failed half way (#339). Otherwise a run
    stays paused for its 30 min pause timeout with Chromium open, and the next tests slow down or hang."""
    made: list[InProcessExecutor] = []
    init = InProcessExecutor.__init__

    def track(self: InProcessExecutor, *args: Any, **kwargs: Any) -> None:
        init(self, *args, **kwargs)
        made.append(self)

    monkeypatch.setattr(InProcessExecutor, "__init__", track)
    yield
    for executor in made:
        with suppress(TimeoutError):
            await asyncio.wait_for(executor.shutdown(), timeout=60)
