import pytest

from app.agent import PlaywrightSession
from app.agent.context import ElementContext, element_context

pytestmark = pytest.mark.anyio


@pytest.fixture
async def page(session: PlaywrightSession) -> PlaywrightSession:
    await session.page.goto("/context")
    return session


@pytest.mark.parametrize(
    ("role", "name", "expected"),
    [
        ("button", "Confirm", ElementContext(container="dialog", name="Create new branch")),
        ("textbox", "Branch Name", ElementContext(container="dialog", name="Create new branch")),
        ("link", "Explore", ElementContext(container="top_bar")),
        ("menuitem", "New File", ElementContext(container="menu")),
        ("textbox", "Description", ElementContext(container="section", name="Basic Settings")),
        ("button", "Update Settings", ElementContext(container="section", name="Basic Settings")),
        # The rewrite drops a section that only repeats the label; here it is still reported as found.
        ("button", "Commit Changes", ElementContext(container="section", name="Commit Changes")),
    ],
)
async def test_container_is_found(
    page: PlaywrightSession, role: str, name: str, expected: ElementContext
) -> None:
    locator = page.page.get_by_role(role, name=name)  # type: ignore[arg-type]

    assert await element_context(locator) == expected


async def test_a_heading_made_only_of_links_is_not_a_section(page: PlaywrightSession) -> None:
    # Gitea's "Labels Milestones" tab strip sits right before the "New Issue" link.
    assert await element_context(page.page.get_by_role("link", name="New Issue")) is None


async def test_no_container_gives_none(page: PlaywrightSession) -> None:
    assert await element_context(page.page.get_by_role("button", name="Alone")) is None


async def test_a_detached_element_gives_none_instead_of_raising(page: PlaywrightSession) -> None:
    gone = page.page.locator("#does-not-exist")
    page.page.set_default_timeout(500)

    assert await element_context(gone) is None
