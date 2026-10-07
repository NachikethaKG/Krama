"""The executor against the real local Gitea (`just up` + `just seed`), following the Phase F walkthrough.

These stop before "Create Repository", so they change nothing in Gitea; creating repos is #29.
"""

import os
from collections.abc import AsyncIterator

import pytest

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig
from app.contracts_gen.common_schema import Action, Target

pytestmark = [pytest.mark.anyio, pytest.mark.gitea]


@pytest.fixture
async def signed_in(gitea: str) -> AsyncIterator[ActionExecutor]:
    async with PlaywrightSession(SessionConfig(base_url=gitea)) as session:
        ex = ActionExecutor(session.page)
        steps = [
            (Action(type="navigate", value="/user/login"), None),
            (
                Action(type="fill", value=os.environ.get("GITEA_DEMO_USER", "demo")),
                Target(role="textbox", name="Username or Email Address"),
            ),
            (
                Action(type="fill", value=os.environ.get("GITEA_DEMO_PASSWORD", "demo-local-only")),
                Target(role="textbox", name="Password"),
            ),
            (Action(type="click"), Target(role="button", name="Sign In")),
            (Action(type="wait"), Target(role="main", name="Dashboard")),
        ]
        for action, target in steps:
            result = await ex.execute(action, target)
            assert result.ok, f"login step {action.type} failed: {result.error}"
        yield ex


async def test_open_create_repo_form_through_the_plus_menu(signed_in: ActionExecutor) -> None:
    ex = signed_in

    menu = await ex.execute(Action(type="click"), Target(role="menu", name="Create…"))
    item = await ex.execute(Action(type="click"), Target(role="menuitem", name="New Repository"))
    repo_name = Target(role="textbox", name="Repository Name")
    name = await ex.execute(Action(type="fill", value="demo-repo"), repo_name)
    init = await ex.execute(Action(type="click"), Target(role="checkbox", name="Initialize Repository"))

    for r in (menu, item, name, init):
        assert r.ok, r.error
        assert r.bbox is not None
    assert menu.url_after == "/"
    assert item.url_after == "/repo/create"
    assert init.url_after == "/repo/create"


async def test_missing_element_on_gitea_is_target_not_found(signed_in: ActionExecutor) -> None:
    result = await signed_in.execute(Action(type="click"), Target(role="button", name="Delete Everything"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "target_not_found"
    assert result.duration_ms < 10_000
