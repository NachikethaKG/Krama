"""Fixtures for observer tests: browser sessions, fake Gitea routes, and live Gitea checks."""

from __future__ import annotations

import os
import urllib.request
from collections.abc import AsyncIterator

import pytest
from playwright.async_api import Browser, BrowserContext, Page, Route, async_playwright

MOCK_GITEA_ORIGIN = "http://gitea.local"

GITEA_HTML_PAGES: dict[str, str] = {
    "/": """<!DOCTYPE html>
<html>
<head><title>Dashboard - Gitea</title></head>
<body>
  <div role="main">
    <h1>Dashboard</h1>
    <a href="/repo/create">New Repository</a>
    <button id="refresh-btn">Refresh</button>
  </div>
</body>
</html>""",
    "/repo/create": """<!DOCTYPE html>
<html>
<head><title>Create a repository - Gitea</title></head>
<body>
  <div role="main">
    <h1>Create a repository</h1>
    <form action="/repo/created" method="post">
      <label for="repo_name">Repository Name *</label>
      <input id="repo_name" name="repo_name" type="text" value="my-test-repo" />

      <label for="pwd">Secret Password</label>
      <input id="pwd" name="pwd" type="password" value="super-secret-password-123" />

      <button type="submit">Create Repository</button>
    </form>
  </div>
</body>
</html>""",
    "/repo/created": """<!DOCTYPE html>
<html>
<head><title>demo/my-test-repo - Gitea</title></head>
<body>
  <div role="main">
    <h1>demo/my-test-repo</h1>
    <p>Repository created successfully.</p>
  </div>
</body>
</html>""",
}


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "gitea: needs the local Gitea from `just up` (skipped if unreachable)")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def gitea_live_url() -> str:
    url = os.environ.get("GITEA_URL", "http://localhost:3001")
    try:
        urllib.request.urlopen(f"{url}/api/healthz", timeout=1)
    except OSError:
        pytest.skip(f"Live Gitea not running at {url}; start with `just up` and `just seed`")
    return url


@pytest.fixture
async def browser_context() -> AsyncIterator[BrowserContext]:
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            base_url=MOCK_GITEA_ORIGIN,
        )
        yield context
        await context.close()
        await browser.close()


@pytest.fixture
async def mock_gitea_page(browser_context: BrowserContext) -> AsyncIterator[Page]:
    page = await browser_context.new_page()

    async def _handle_route(route: Route) -> None:
        url = route.request.url
        path = url.removeprefix(MOCK_GITEA_ORIGIN).split("?")[0] or "/"
        if path in GITEA_HTML_PAGES:
            await route.fulfill(
                status=200,
                content_type="text/html; charset=utf-8",
                body=GITEA_HTML_PAGES[path],
            )
        elif path == "/api/error":
            await route.fulfill(status=500, content_type="application/json", body='{"error": "fail"}')
        else:
            await route.fulfill(status=404, content_type="text/html", body="<h1>404 Not Found</h1>")

    await browser_context.route(f"{MOCK_GITEA_ORIGIN}/**", _handle_route)
    yield page
