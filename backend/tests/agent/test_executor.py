import pytest

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig
from app.contracts_gen.common_schema import Action, Target

pytestmark = pytest.mark.anyio


async def test_session_uses_configured_viewport() -> None:
    async with PlaywrightSession(SessionConfig(base_url="http://krama.test", viewport_width=800)) as s:
        assert s.page.viewport_size == {"width": 800, "height": 800}


async def test_session_is_closed_after_exit() -> None:
    session = PlaywrightSession(SessionConfig(base_url="http://krama.test"))
    async with session:
        pass
    with pytest.raises(RuntimeError):
        _ = session.page


async def test_click_returns_timing_bbox_and_url(executor: ActionExecutor) -> None:
    result = await executor.execute(Action(type="click"), Target(role="link", name="Go to form"))

    assert result.ok, result.error
    assert result.action == "click"
    assert result.url_after == "/form"
    assert result.duration_ms >= 0
    assert result.bbox is not None
    x, y, width, height = result.bbox
    assert width > 0 and height > 0 and x >= 0 and y >= 0


async def test_bbox_is_in_page_coordinates(executor: ActionExecutor, session: PlaywrightSession) -> None:
    await session.page.evaluate("window.scrollTo(0, 1500)")

    result = await executor.execute(Action(type="click"), Target(role="button", name="Far away"))

    assert result.ok, result.error
    assert result.bbox is not None
    # The button sits below a 2000px spacer: in viewport coordinates it would be ~500px, not > 2000.
    assert result.bbox[1] > 2000


async def test_fill_matches_name_as_substring(executor: ActionExecutor, session: PlaywrightSession) -> None:
    await executor.execute(Action(type="navigate", value="/form"))

    result = await executor.execute(
        Action(type="fill", value="demo-repo"), Target(role="textbox", name="Repository Name")
    )

    assert result.ok, result.error
    assert await session.page.get_by_role("textbox").input_value() == "demo-repo"


async def test_select_option(executor: ActionExecutor, session: PlaywrightSession) -> None:
    await executor.execute(Action(type="navigate", value="/form"))

    license_box = Target(role="combobox", name="License")
    result = await executor.execute(Action(type="select", value="MIT"), license_box)

    assert result.ok, result.error
    assert await session.page.get_by_role("combobox").input_value() == "MIT"


async def test_navigate_to_path(executor: ActionExecutor) -> None:
    result = await executor.execute(Action(type="navigate", value="/form"))

    assert result.ok, result.error
    assert result.url_after == "/form"
    assert result.bbox is None


async def test_press_enter_submits_form(executor: ActionExecutor) -> None:
    await executor.execute(Action(type="navigate", value="/form"))
    await executor.execute(Action(type="fill", value="x"), Target(role="textbox", name="Repository Name"))

    repo_name = Target(role="textbox", name="Repository")
    result = await executor.execute(Action(type="press", value="Enter"), repo_name)
    await executor.execute(Action(type="wait"), Target(role="heading", name="Done"))

    assert result.ok, result.error
    assert (await executor.execute(Action(type="wait"))).url_after == "/done"


async def test_wait_for_element_that_appears_later(executor: ActionExecutor) -> None:
    await executor.execute(Action(type="click"), Target(role="button", name="Reveal later"))

    result = await executor.execute(Action(type="wait"), Target(role="status"))

    assert result.ok, result.error
    assert result.bbox is not None


async def test_selector_fallback(executor: ActionExecutor) -> None:
    result = await executor.execute(Action(type="click"), Target(selector="#far"))

    assert result.ok, result.error


async def test_missing_target_fails_with_target_not_found(executor: ActionExecutor) -> None:
    result = await executor.execute(Action(type="click"), Target(role="button", name="Does not exist"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "target_not_found"
    assert 900 <= result.duration_ms < 5_000  # the 1 s test timeout, not Playwright's 30 s default


async def test_ambiguous_target_is_reported_not_guessed(executor: ActionExecutor) -> None:
    result = await executor.execute(Action(type="click"), Target(role="button", name="Save"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "ambiguous_target"


async def test_hidden_element_times_out(executor: ActionExecutor) -> None:
    # Present in the DOM but hidden, so it never becomes visible: a timeout, not "not found".
    result = await executor.execute(Action(type="click"), Target(selector="#late"))

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "timeout"


@pytest.mark.parametrize(
    ("action", "target"),
    [
        (Action(type="click"), None),
        (Action(type="fill"), Target(role="textbox", name="Repository Name")),
        (Action(type="fill", value="x"), Target(name="Repository Name")),
        (Action(type="navigate", value="https://example.com/"), None),
        (Action(type="navigate", value="//example.com/"), None),
        (Action(type="press"), None),
    ],
)
async def test_invalid_actions_are_rejected_before_touching_the_page(
    executor: ActionExecutor, action: Action, target: Target | None
) -> None:
    result = await executor.execute(action, target)

    assert not result.ok
    assert result.error is not None
    assert result.error.code == "invalid_action"
    assert result.url_after == "/"


async def test_fill_value_never_appears_in_errors(executor: ActionExecutor) -> None:
    secret = "s3cret-password-value"

    result = await executor.execute(Action(type="fill", value=secret), Target(role="button", name="Reveal"))

    assert not result.ok
    assert result.error is not None
    assert secret not in result.error.message
    assert secret not in result.model_dump_json()
