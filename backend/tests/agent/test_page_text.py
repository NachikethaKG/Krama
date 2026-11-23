"""The page an LLM sees: the whole body, trimmed to a budget (#461)."""

import pytest
from playwright.async_api import Route

from app.agent import PlaywrightSession, SessionConfig, page_snapshot
from app.agent.page_text import trim_snapshot
from tests.agent.conftest import FAKE_SITE

pytestmark = pytest.mark.anyio

ARTICLE = "<p>" + "A very long paragraph about the history of computing. " * 40 + "</p>"
HEADER = """<header><form role="search"><label>Search the site <input type="search"></label>
    <button>Search</button></form><nav><a href="/docs">Docs</a></nav></header>"""
PAGES = {
    "/header": f"<title>Home</title>{HEADER}<main><h1>Welcome</h1>{ARTICLE}</main>",
    "/huge": f"<title>Article</title>{HEADER}<main><h1>Article</h1>{ARTICLE * 150}"
    "<h2>See also</h2><a href='/more'>More reading</a><label>Comment <textarea></textarea></label></main>",
}


async def serve(route: Route) -> None:
    path = route.request.url.removeprefix(FAKE_SITE)
    await route.fulfill(status=200, content_type="text/html", body=PAGES.get(path, "<title>404</title>"))


async def snapshot_of(path: str, budget: int = 24_000) -> str:
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        await session.context.route(f"{FAKE_SITE}/**", serve)
        await session.page.goto(path)
        return await page_snapshot(session.page, budget)


async def test_the_header_search_outside_main_is_shown() -> None:
    # Spike #457: Wikipedia's search box sits in the header; the planner only got <main> and never saw it.
    snapshot = await snapshot_of("/header")

    assert 'searchbox "Search the site"' in snapshot
    assert 'link "Docs"' in snapshot
    assert 'heading "Welcome"' in snapshot


async def test_a_huge_page_fits_the_budget_and_keeps_its_controls() -> None:
    snapshot = await snapshot_of("/huge", budget=8_000)

    assert len(snapshot) <= 8_000
    assert 'searchbox "Search the site"' in snapshot
    assert 'heading "See also"' in snapshot
    assert 'link "More reading"' in snapshot
    assert 'textbox "Comment"' in snapshot
    assert "history of computing" not in snapshot  # the long text went first


def test_a_small_snapshot_is_unchanged() -> None:
    text = '- main:\n  - heading "Todos" [level=1]\n  - textbox "What needs to be done?"'
    assert trim_snapshot(text, 1_000) == text


def test_trimming_drops_urls_then_text_then_cuts() -> None:
    links = "\n".join(f'  - link "Page {i}":\n    - /url: /wiki/Page_{i}' for i in range(200))
    texts = "\n".join(f"  - paragraph: {'words ' * 30}" for _ in range(200))
    snapshot = f'- banner:\n  - searchbox "Search"\n- main:\n{texts}\n{links}'

    without_urls = trim_snapshot(snapshot, len(snapshot) - 100)
    assert "/url:" not in without_urls and "paragraph" in without_urls

    outline = trim_snapshot(snapshot, 6_000)
    assert "paragraph" not in outline and 'link "Page 199"' in outline
    assert outline.startswith('- banner:\n  - searchbox "Search"\n- main:')

    cut = trim_snapshot(snapshot, 2_000)
    assert len(cut) <= 2_000
    assert 'searchbox "Search"' in cut
    assert cut.endswith("more lines]")


def test_a_very_long_line_is_shortened() -> None:
    line = '- link "' + "x" * 1_000 + '"'
    out = trim_snapshot("\n".join([line] * 50), 20_000)
    assert max(len(x) for x in out.splitlines()) <= 200
