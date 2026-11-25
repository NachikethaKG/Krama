"""The browser session's start page (#462)."""

import asyncio
from urllib.parse import urlsplit

import pytest
from playwright.async_api import Route

from app.agent import PlaywrightSession, SessionConfig, open_start_page, page_snapshot, start_path
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


async def test_the_start_page_is_read_after_its_data_arrives() -> None:
    # #482: Trello's start page is a spinner until its data loads; the planner saw only "- img" and asked
    # the signed-in owner to log in.
    app_html = """<title>App</title><main><img alt="Loading"></main>
        <script>fetch("/data").then(r => r.text()).then(t => {
          document.querySelector("main").innerHTML = "<h1>" + t + "</h1>" })</script>"""

    async def serve(route: Route) -> None:
        if urlsplit(route.request.url).path == "/data":
            await asyncio.sleep(1.5)
            await route.fulfill(status=200, content_type="text/plain", body="Your inbox")
        else:
            await route.fulfill(status=200, content_type="text/html", body=app_html)

    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        await session.context.route(f"{FAKE_SITE}/**", serve)

        assert await open_start_page(session.page)

        assert "Your inbox" in await page_snapshot(session.page)


async def test_twin_search_boxes_take_the_first() -> None:
    # The Python docs show "Quick search" in the header and the sidebar; without vision the fill failed as
    # ambiguous (Phase 7, #470). Two same-named search boxes do the same thing.
    from app.agent import ActionExecutor
    from app.contracts_gen.common_schema import Action, Target

    page_html = """<title>Docs</title><header><input type="search" aria-label="Quick search"></header>
        <main><h1>Docs</h1></main><aside><input type="search" aria-label="Quick search"></aside>"""

    async def serve(route: Route) -> None:
        await route.fulfill(status=200, content_type="text/html", body=page_html)

    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        await session.context.route(f"{FAKE_SITE}/**", serve)
        await session.page.goto("/")
        executor = ActionExecutor(session.page)

        result = await executor.execute(
            Action(type="fill", value="asyncio.gather"), Target(role="searchbox", name="Quick search")
        )

        assert result.ok, result.error
        values = await session.page.get_by_role("searchbox", name="Quick search").evaluate_all(
            "els => els.map(e => e.value)"
        )
        assert values == ["asyncio.gather", ""]
