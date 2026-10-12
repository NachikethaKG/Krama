"""The locator fallback chain (#54): role/name → label → text → selector → vision pick."""

import os

import pytest
from playwright.async_api import Page

from app.agent import ActionExecutor, PlaywrightSession
from app.agent.vision import SENSITIVE_FIELDS, GeminiVisionLocator, VisionResult, box_center, build_prompt
from app.contracts_gen.common_schema import Action, Target
from app.llm import FakeProvider, FakeResponse, LLMAttempt

pytestmark = pytest.mark.anyio

CLICK = Action(type="click")


class ScriptedVision:
    """Points at a fixed spot, or at the centre of the element a test chose, and records each call."""

    def __init__(self, point: tuple[float, float] | None = None, *, at: str | None = None) -> None:
        self._point, self._at = point, at
        self.calls: list[tuple[Target, str | None]] = []

    async def point(self, page: Page, target: Target, instruction: str | None) -> VisionResult:
        self.calls.append((target, instruction))
        point = self._point
        if self._at is not None:
            box = await page.locator(self._at).bounding_box()
            assert box is not None
            point = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        attempt = LLMAttempt(model="scripted", status="ok", latency_ms=0)
        return VisionResult(point=point, model="scripted", attempts=[attempt])


async def on_locate_page(session: PlaywrightSession, vision: ScriptedVision | None = None) -> ActionExecutor:
    await session.page.goto("/locate")
    return ActionExecutor(session.page, vision=vision)


async def test_role_and_name_is_tried_first(executor: ActionExecutor) -> None:
    result = await executor.execute(CLICK, Target(role="link", name="Go to form"))

    assert result.ok and result.strategy == "role"


async def test_renamed_accessible_name_falls_back_to_visible_text(session: PlaywrightSession) -> None:
    # The plan says button "New Repository"; the button's aria-label now overrides its accessible name.
    executor = await on_locate_page(session)

    result = await executor.execute(CLICK, Target(role="button", name="New Repository"))

    assert result.ok, result.error
    assert result.strategy == "text"
    assert await session.page.title() == "renamed"


async def test_changed_role_falls_back_to_visible_text(session: PlaywrightSession) -> None:
    executor = await on_locate_page(session)

    result = await executor.execute(CLICK, Target(role="button", name="Open settings"))  # it is a link now

    assert result.ok and result.strategy == "text"
    assert await session.page.title() == "link"


async def test_wrong_role_for_a_labelled_field_falls_back_to_the_label(session: PlaywrightSession) -> None:
    executor = await on_locate_page(session)

    result = await executor.execute(
        Action(type="fill", value="demo-repo"), Target(role="combobox", name="Repository Name")
    )

    assert result.ok, result.error
    assert result.strategy == "label"
    assert await session.page.get_by_label("Repository Name").input_value() == "demo-repo"


async def test_selector_is_used_when_role_and_name_find_nothing(session: PlaywrightSession) -> None:
    executor = await on_locate_page(session)

    result = await executor.execute(
        CLICK, Target(role="button", name="Gone", selector="section:nth-of-type(2) button")
    )

    assert result.ok and result.strategy == "selector"
    assert await session.page.title() == "published"


async def test_several_matches_without_vision_stay_ambiguous(session: PlaywrightSession) -> None:
    executor = await on_locate_page(session)

    result = await executor.execute(CLICK, Target(role="button", name="Save"))

    assert not result.ok and result.error is not None
    assert result.error.code == "ambiguous_target"
    assert result.strategy is None
    assert await session.page.title() == "Locate"  # nothing was clicked


async def test_vision_picks_one_of_several_matches(session: PlaywrightSession) -> None:
    vision = ScriptedVision(at="section:nth-of-type(2) button")
    executor = await on_locate_page(session, vision)

    result = await executor.execute(
        CLICK, Target(role="button", name="Save"), instruction="Click Save in the Publish section."
    )

    assert result.ok, result.error
    assert result.strategy == "vision"
    assert await session.page.title() == "published"
    assert vision.calls == [(Target(role="button", name="Save"), "Click Save in the Publish section.")]
    assert [a.model for a in result.llm_attempts] == ["scripted"]


async def test_vision_pointing_at_no_candidate_clicks_nothing(session: PlaywrightSession) -> None:
    executor = await on_locate_page(session, ScriptedVision(point=(5, 5)))  # top-left corner: no Save there

    result = await executor.execute(CLICK, Target(role="button", name="Save"))

    assert not result.ok and result.error is not None and result.error.code == "ambiguous_target"
    assert len(result.llm_attempts) == 1
    assert await session.page.title() == "Locate"


async def test_vision_is_not_asked_when_one_strategy_is_unique(session: PlaywrightSession) -> None:
    vision = ScriptedVision(point=(5, 5))
    executor = await on_locate_page(session, vision)

    result = await executor.execute(CLICK, Target(role="button", name="New Repository"))

    assert result.ok and result.strategy == "text"
    assert vision.calls == []


async def test_a_missing_element_costs_one_timeout_not_one_per_strategy(
    fast_fail_executor: ActionExecutor,
) -> None:
    result = await fast_fail_executor.execute(
        CLICK, Target(role="button", name="Nowhere", selector="#nowhere")
    )

    assert not result.ok and result.error is not None and result.error.code == "target_not_found"
    assert result.duration_ms < 2_500  # 1 s action timeout; 4 strategies would take 4 s


def test_box_center_uses_css_viewport_pixels() -> None:
    # The research example: "New Repository" at the top right of a 1280x800 viewport.
    assert box_center([230, 950, 250, 962], 1280, 800) == pytest.approx((1223.68, 192.0))
    assert box_center([10, 10, 10, 20], 1280, 800) is None  # empty box
    assert box_center(None, 1280, 800) is None


def test_prompt_carries_only_the_planned_target() -> None:
    prompt = build_prompt(Target(role="button", name="Save"), "Click Save in the Publish section.")

    assert "ARIA role: button" in prompt and "Save" in prompt and "Publish section" in prompt


async def test_gemini_locator_masks_secrets_and_scales_the_box(session: PlaywrightSession) -> None:
    await session.page.goto("/locate")
    llm = FakeProvider([FakeResponse(name="box", response={"found": True, "box_2d": [500, 250, 600, 750]})])

    result = await GeminiVisionLocator(llm).point(session.page, Target(role="button", name="Save"), None)

    assert result.point == pytest.approx((640.0, 440.0))  # centre of the box on a 1280x800 viewport
    [image] = llm.images
    assert image is not None and image.startswith(b"\x89PNG")
    masked = session.page.locator(SENSITIVE_FIELDS)
    assert await masked.count() == 1  # the password, not the "Notes" field
    assert await masked.get_attribute("name") == "password"


async def test_gemini_locator_not_found_is_no_point(session: PlaywrightSession) -> None:
    llm = FakeProvider([FakeResponse(name="none", response={"found": False})])

    result = await GeminiVisionLocator(llm).point(session.page, Target(role="button", name="Save"), None)

    assert result.point is None and result.error is None


@pytest.mark.skipif(
    os.environ.get("KRAMA_LIVE_GEMINI") != "1", reason="live Gemini call; set KRAMA_LIVE_GEMINI=1"
)
async def test_live_gemini_picks_the_save_in_the_publish_section(session: PlaywrightSession) -> None:
    from app.config import get_settings
    from app.llm import DEFAULT_MODELS, GeminiProvider

    llm = GeminiProvider(get_settings().gemini_api_key, DEFAULT_MODELS)
    executor = await on_locate_page(session)
    executor = ActionExecutor(session.page, vision=GeminiVisionLocator(llm))

    result = await executor.execute(
        CLICK, Target(role="button", name="Save"), instruction="Click Save in the Publish section."
    )

    assert result.ok, (result.error, result.llm_attempts)
    assert result.strategy == "vision"
    assert await session.page.title() == "published"
