"""#181: the port field `aria_excerpt` carries the whole masked snapshot, not the first 500 characters."""

from __future__ import annotations

import pytest
from playwright.async_api import Page

from app.observer import Observation, PageObserver

SECRET = "super-secret-password-123"
# A form long enough that its ARIA snapshot is well over 500 characters, with the important parts at the end.
LONG_FORM = (
    '<div role="main"><h1>Create a repository</h1>'
    + "".join(
        f'<label>Optional field number {i} <input name="f{i}" value="value {i}"></label>' for i in range(20)
    )
    + f'<label>Password <input type="password" value="{SECRET}"></label>'
    + '<label><input type="checkbox" checked> Initialize Repository</label>'
    + "<button>Create Repository</button></div>"
)


def test_create_keeps_the_whole_snapshot_in_the_excerpt() -> None:
    snapshot = "\n".join(f'- textbox "Field {i}": value {i}' for i in range(100))

    obs = Observation.create(url="/repo/create", aria_snapshot=snapshot)

    assert len(snapshot) > 500
    assert obs.aria_excerpt == snapshot


def test_explicit_excerpt_still_wins() -> None:
    obs = Observation.create(url="/", aria_snapshot="- main: full", aria_excerpt="- main: chosen")

    assert obs.aria_excerpt == "- main: chosen"


@pytest.mark.anyio
async def test_capture_sends_the_full_masked_snapshot_through_the_port(mock_gitea_page: Page) -> None:
    await mock_gitea_page.set_content(LONG_FORM)

    obs = await PageObserver().capture(mock_gitea_page)

    assert len(obs.aria_excerpt) > 500
    assert obs.aria_excerpt == obs.aria_snapshot
    # elements at the end of the page are still there for the verifier
    assert 'checkbox "Initialize Repository" [checked]' in obs.aria_excerpt
    assert 'button "Create Repository"' in obs.aria_excerpt
    # and the password is masked in the field that crosses the port
    assert SECRET not in obs.aria_excerpt
