"""The browser session's start page (#462)."""

from urllib.parse import urlsplit

import pytest
from playwright.async_api import Route

from app.agent import PlaywrightSession, SessionConfig, open_start_page, start_path
from tests.agent.conftest import FAKE_SITE

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("http://localhost:3001", "/"),
        ("https://github.com/", "/"),
        ("https://demo.playwright.dev/todomvc", "/todomvc"),
        ("https://docs.python.org/3/", "/3/"),
        ("https://www.openstreetmap.org/search?query=Bengaluru", "/search?query=Bengaluru"),
    ],
)
def test_start_path_keeps_the_target_path(target: str, expected: str) -> None:
    assert start_path(target) == expected


async def test_a_target_under_a_path_starts_there_not_at_the_site_root() -> None:
    # Spike #457: https://demo.playwright.dev/todomvc opened demo.playwright.dev/ and the planner asked where
    # the todo list was.
    async def serve(route: Route) -> None:
        path = urlsplit(route.request.url).path
        title = {"/": "Site root", "/todomvc": "Todos"}.get(path, "Not found")
        await route.fulfill(status=200, content_type="text/html", body=f"<title>{title}</title><main></main>")

    target = f"{FAKE_SITE}/todomvc"
    async with PlaywrightSession(SessionConfig(base_url=target)) as session:
        await session.context.route(f"{FAKE_SITE}/**", serve)

        assert await open_start_page(session.page, start_path(target))

        assert urlsplit(session.page.url).path == "/todomvc"
        assert await session.page.title() == "Todos"
