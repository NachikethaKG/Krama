"""Cookie and consent banners are answered by code with the least-sharing choice, never as a step (#493)."""

import pytest
from playwright.async_api import Page, Route

from app.agent import PlaywrightSession, SessionConfig, open_start_page
from app.agent.consent import clear_consent
from tests.agent.conftest import FAKE_SITE

pytestmark = pytest.mark.anyio

# Clicking a button records the choice and removes its box, like a real banner.
SCRIPT = """<script>
  window.choices = [];
  document.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    window.choices.push(b.textContent); b.closest("[data-box]").remove(); }));
</script>"""


def banner(*buttons: str, text: str = "We use cookies to improve your experience.") -> str:
    items = "".join(f"<button>{b}</button>" for b in buttons)
    return f'<div role="dialog" aria-label="Cookie notice" data-box><p>{text}</p>{items}</div>'


async def open_page(session: PlaywrightSession, body: str) -> Page:
    html = f"<title>Site</title><main><h1>Home</h1></main>{body}{SCRIPT}"

    async def serve(route: Route) -> None:
        await route.fulfill(status=200, content_type="text/html", body=html)

    await session.context.route(f"{FAKE_SITE}/**", serve)
    await session.page.goto("/")
    return session.page


async def choices(page: Page) -> list[str]:
    result: list[str] = await page.evaluate("window.choices")
    return result


async def test_the_least_sharing_choice_is_taken() -> None:
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        page = await open_page(session, banner("Accept all", "Only necessary", "Preferences"))

        assert await clear_consent(page) == 1

        assert await choices(page) == ["Only necessary"]
        assert await page.get_by_role("dialog").count() == 0


async def test_a_banner_that_only_offers_accept_is_left_alone() -> None:
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        page = await open_page(session, banner("Accept all", "Manage settings"))

        assert await clear_consent(page) == 0

        assert await choices(page) == []
        assert await page.get_by_role("dialog").is_visible()


async def test_a_decline_button_that_isnt_about_cookies_is_left_alone() -> None:
    # An invitation's "Decline", on a page whose long text mentions cookies elsewhere (a footer link).
    invite = (
        "<div data-box><p>Asha invited you to the board.</p>"
        "<button>Accept</button><button>Decline</button></div>"
    )
    footer = "<footer>" + "Lots of page text. " * 200 + "<a href='#'>Cookie settings</a></footer>"
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        page = await open_page(session, f"<section>{invite}{footer}</section>")

        assert await clear_consent(page) == 0

        assert await choices(page) == []


async def test_two_copies_of_a_notice_are_both_answered() -> None:
    # Trello showed the same Atlassian notice twice in its ARIA snapshot (#482).
    two = banner("Accept all", "Only necessary") + banner("Accept all", "Only necessary")
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        page = await open_page(session, two)

        assert await clear_consent(page) == 2

        assert await choices(page) == ["Only necessary", "Only necessary"]


@pytest.mark.parametrize("button", ["Reject all", "Decline", "Use necessary cookies only", "Only essential"])
async def test_other_least_sharing_names(button: str) -> None:
    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        page = await open_page(session, banner("Accept all cookies", button))

        assert await clear_consent(page) == 1

        assert await choices(page) == [button]


async def test_the_start_page_opens_without_its_banner() -> None:
    html = f"<title>Site</title><main><h1>Home</h1></main>{banner('Accept all', 'Reject all')}{SCRIPT}"

    async def serve(route: Route) -> None:
        await route.fulfill(status=200, content_type="text/html", body=html)

    async with PlaywrightSession(SessionConfig(base_url=FAKE_SITE)) as session:
        await session.context.route(f"{FAKE_SITE}/**", serve)

        assert await open_start_page(session.page)

        assert await choices(session.page) == ["Reject all"]
