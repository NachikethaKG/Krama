import os
import urllib.request
from collections.abc import AsyncIterator

import pytest
from playwright.async_api import Route

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig

FAKE_SITE = "http://krama.test"

# A tiny fake site, served through Playwright's request routing (no server, no network).
PAGES: dict[str, str] = {
    "/": """<title>Home</title><main>
        <h1>Home</h1>
        <a href="/form">Go to form</a>
        <button onclick="document.getElementById('late').hidden = false">Reveal</button>
        <button onclick="setTimeout(() => { document.getElementById('late').hidden = false }, 300)">
          Reveal later</button>
        <p id="late" hidden role="status">Revealed</p>
        <button>Save</button><button>Save</button>
        <div style="height: 2000px"></div>
        <button id="far">Far away</button>
    </main>""",
    "/form": """<title>Form</title><main>
        <form action="/done" method="get">
          <label>Repository Name * <input name="repo"></label>
          <label>License <select name="license"><option>None</option><option>MIT</option></select></label>
          <button type="submit">Create Repository</button>
        </form>
    </main>""",
    "/done": "<title>Done</title><main><h1>Done</h1></main>",
}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "gitea: needs the local Gitea from `just up` (skipped if unreachable)")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _serve(route: Route) -> None:
    path = route.request.url.removeprefix(FAKE_SITE).split("?")[0] or "/"
    if path in PAGES:
        await route.fulfill(status=200, content_type="text/html", body=PAGES[path])
    else:
        await route.fulfill(status=404, content_type="text/html", body="<title>Not found</title>")


@pytest.fixture
async def session() -> AsyncIterator[PlaywrightSession]:
    # Short action timeout so failure cases stay fast.
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE, action_timeout_ms=1_000)) as s:
        await s.context.route(f"{FAKE_SITE}/**", _serve)
        await s.page.goto("/")
        yield s


@pytest.fixture
def executor(session: PlaywrightSession) -> ActionExecutor:
    return ActionExecutor(session.page)


def gitea_url() -> str:
    return os.environ.get("GITEA_URL", "http://localhost:3001")


@pytest.fixture(scope="session")
def gitea() -> str:
    url = gitea_url()
    try:
        urllib.request.urlopen(f"{url}/api/healthz", timeout=2)
    except OSError:
        pytest.skip(f"Gitea not reachable at {url}; start it with `just up` and `just seed`")
    return url
