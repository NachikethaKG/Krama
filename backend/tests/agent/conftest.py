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
    # Elements that drifted away from what a plan says (#54): the locator chain must still find them.
    "/locate": """<title>Locate</title><main>
        <button aria-label="Add a repo" onclick="document.title = 'renamed'">
          New Repository</button>
        <a href="#" onclick="document.title = 'link'; return false">Open settings</a>
        <input aria-label="Repository Name">
        <section><h2>Draft</h2><button onclick="document.title = 'draft saved'">Save</button></section>
        <div style="height: 120px"></div>
        <section><h2>Publish</h2><button onclick="document.title = 'published'">Save</button></section>
        <label>Password <input type="password" name="password" value="hunter2"></label>
        <label>Notes <input name="notes" value="visible"></label>
    </main>""",
    # A Fomantic-UI style dialog outside <main> without role=dialog, as Gitea renders it (#78).
    "/dialogs": """<title>Branches</title>
        <main><h1>Branches</h1><div role="dialog"><button>Inside main</button></div></main>
        <div class="ui modal visible"><div class="header">Create new branch</div>
          <label>Branch Name * <input></label><button>Confirm</button></div>
        <div class="ui modal" hidden><button>Closed dialog</button></div>""",
    # Where elements sit, for the step text (#73): dialog, top bar, dropdown menu, form sections, tab strip.
    "/context": """<title>Settings - demo-repo</title>
        <nav id="navbar"><a href="/">Explore</a></nav>
        <main>
          <h4 class="tabs"><a href="#">Labels</a> <a href="#">Milestones</a></h4>
          <div><a href="#">New Issue</a></div>
          <h4>Basic Settings</h4>
          <div class="segment"><form><label>Description <textarea></textarea></label>
            <button>Update Settings</button></form></div>
          <h3>Commit Changes</h3>
          <div><button>Commit Changes</button></div>
          <div style="position: relative"><div role="menu" style="position: absolute">
            <a role="menuitem" href="#">New File</a></div></div>
          <div class="ui modal" role="dialog"><div class="header">Create new branch</div>
            <label>Branch Name * <input></label><button>Confirm</button></div>
          <button>Alone</button>
        </main>""",
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


async def _open_fake_site(action_timeout_ms: int) -> AsyncIterator[PlaywrightSession]:
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE, action_timeout_ms=action_timeout_ms)) as s:
        await s.context.route(f"{FAKE_SITE}/**", _serve)
        await s.page.goto("/")
        yield s


@pytest.fixture
async def session() -> AsyncIterator[PlaywrightSession]:
    # The production timeout: Playwright's stability check can take over 1 s on a busy laptop.
    async for s in _open_fake_site(SessionConfig.action_timeout_ms):
        yield s


@pytest.fixture
def executor(session: PlaywrightSession) -> ActionExecutor:
    return ActionExecutor(session.page)


@pytest.fixture
async def fast_fail_executor() -> AsyncIterator[ActionExecutor]:
    """A 1 s action timeout, only for tests whose action is meant to fail (keeps them fast)."""
    async for s in _open_fake_site(1_000):
        yield ActionExecutor(s.page)


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
