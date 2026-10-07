import time
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, ConfigDict

from app.contracts_gen.common_schema import Action, ActionType, BoundingBox, Target

type ActionErrorCode = Literal[
    "invalid_action", "target_not_found", "ambiguous_target", "timeout", "action_failed"
]

_NEEDS_TARGET: frozenset[str] = frozenset({"click", "fill", "select"})
_NEEDS_VALUE: frozenset[str] = frozenset({"fill", "select", "navigate", "press"})


class ActionError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ActionErrorCode
    # Never contains the action's value: fill values can be passwords.
    message: str


class ActionResult(BaseModel):
    """What happened when one action ran. Agent-internal; the run log and the API build on it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: ActionType
    ok: bool
    started_at: datetime
    duration_ms: int
    bbox: BoundingBox | None = None
    """The resolved element in page coordinates (CSS px), measured just before acting. None without target."""
    url_after: str
    """URL path after the action (no scheme or host), like `url_matches` in the contract."""
    error: ActionError | None = None


class _InvalidActionError(Exception):
    pass


class ActionExecutor:
    """Runs contract actions (click / fill / select / navigate / press / wait) on one page.

    Elements are found by ARIA role + accessible name (substring match, so "Repository Name" finds
    "Repository Name *"), falling back to the CSS selector. Failures come back as `ActionResult(ok=False)`
    with a typed error code; the executor never raises for a failed action.

    It does not decide whether an action is allowed: destructive actions must pass the policy layer
    before they reach `execute`.
    """

    def __init__(self, page: Page) -> None:
        self._page = page

    async def execute(self, action: Action, target: Target | None = None) -> ActionResult:
        started_at = datetime.now(UTC)
        t0 = time.perf_counter()
        bbox: BoundingBox | None = None
        locator: Locator | None = None
        error: ActionError | None = None
        try:
            _validate(action, target)
            if target is not None and (target.role or target.selector):
                locator = self._locate(target)
                await locator.wait_for(state="visible")
                bbox = await self._page_bbox(locator)
            await self._perform(action, locator)
        except _InvalidActionError as e:
            error = ActionError(code="invalid_action", message=str(e))
        except PlaywrightTimeoutError as e:
            missing = locator is not None and await locator.count() == 0
            error = ActionError(code="target_not_found" if missing else "timeout", message=_first_line(e))
        except PlaywrightError as e:
            ambiguous = "strict mode violation" in str(e)
            code: ActionErrorCode = "ambiguous_target" if ambiguous else "action_failed"
            error = ActionError(code=code, message=_first_line(e))
        return ActionResult(
            action=action.type,
            ok=error is None,
            started_at=started_at,
            duration_ms=round((time.perf_counter() - t0) * 1000),
            bbox=bbox,
            url_after=urlsplit(self._page.url).path or "/",
            error=error,
        )

    def _locate(self, target: Target) -> Locator:
        if target.role:
            # Roles come from ARIA snapshots / the LLM as plain strings; Playwright checks them at runtime.
            return self._page.get_by_role(target.role, name=target.name)  # type: ignore[arg-type]
        assert target.selector is not None
        return self._page.locator(target.selector)

    async def _perform(self, action: Action, locator: Locator | None) -> None:
        value = action.value
        match action.type:
            case "click":
                assert locator is not None
                await locator.click()
            case "fill":
                assert locator is not None and value is not None
                await locator.fill(value)
            case "select":
                assert locator is not None and value is not None
                await locator.select_option(value)
            case "navigate":
                assert value is not None
                await self._page.goto(value, wait_until="domcontentloaded")
            case "press":
                assert value is not None
                if locator is not None:
                    await locator.press(value)
                else:
                    await self._page.keyboard.press(value)
            case "wait":
                # With a target, waiting for it to be visible already happened above.
                if locator is None:
                    await self._page.wait_for_load_state("domcontentloaded")

    async def _page_bbox(self, locator: Locator) -> BoundingBox | None:
        box = await locator.bounding_box()
        if box is None:
            return None
        # bounding_box() is relative to the viewport; the contract wants page coordinates.
        scroll_x, scroll_y = await self._page.evaluate("[window.scrollX, window.scrollY]")
        return (box["x"] + scroll_x, box["y"] + scroll_y, box["width"], box["height"])


def _validate(action: Action, target: Target | None) -> None:
    has_target = target is not None and bool(target.role or target.selector)
    if target is not None and target.name and not (target.role or target.selector):
        raise _InvalidActionError("target has a name but no role or selector")
    if action.type in _NEEDS_TARGET and not has_target:
        raise _InvalidActionError(f"{action.type} needs a target with a role or a selector")
    if action.type in _NEEDS_VALUE and action.value is None:
        raise _InvalidActionError(f"{action.type} needs a value")
    if action.type == "navigate" and not (action.value or "").startswith("/"):
        # Only paths on the site under test; a full URL could leave it.
        raise _InvalidActionError("navigate takes a URL path starting with '/', not a full URL")
    if action.type == "navigate" and (action.value or "").startswith("//"):
        raise _InvalidActionError("navigate takes a URL path, not a protocol-relative URL")


def _first_line(e: Exception) -> str:
    return str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
