import re
import time
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import FloatRect, Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import BaseModel, ConfigDict

from app.agent.candidates import Candidate, role_candidates
from app.agent.context import ElementContext, element_context
from app.agent.vision import VisionLocator
from app.contracts_gen.common_schema import Action, ActionType, BoundingBox, ScrollOffset, Target
from app.llm import LLMAttempt

type ActionErrorCode = Literal[
    "invalid_action", "target_not_found", "ambiguous_target", "timeout", "action_failed"
]
type LocatorStrategy = Literal["role", "label", "text", "selector", "form", "vision"]
"""How the target was found: ARIA role + name, aria-label/<label>, visible text, CSS selector, or among
several role/text matches: the one in the form the previous step filled in, or a vision pick."""

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
    scroll: ScrollOffset | None = None
    """Window scroll when the action ran: with a target, after scrolling it into view (the scroll the action
    itself uses); without one, after the action. `bbox - scroll` is the element's box on screen."""
    url_after: str
    """URL path after the action (no scheme or host), like `url_matches` in the contract."""
    strategy: LocatorStrategy | None = None
    """Which locator strategy found the target. None without target, or if nothing was found."""
    context: ElementContext | None = None
    """The dialog, menu, top bar or form section the target sits in, read before acting (for step text)."""
    llm_attempts: list[LLMAttempt] = []
    """LLM requests made by the vision fallback (for the run log and the benchmark)."""
    candidates: list[Candidate] = []
    """After `target_not_found` / `ambiguous_target`: the visible elements with the planned role (#109)."""
    error: ActionError | None = None


class _InvalidActionError(Exception):
    pass


class _UnresolvedTargetError(Exception):
    def __init__(self, code: ActionErrorCode, message: str) -> None:
        super().__init__(message)
        self.code: ActionErrorCode = code


class ActionExecutor:
    """Runs contract actions (click / fill / select / navigate / press / wait) on one page.

    The target is found by a fallback chain, one try per strategy
    (docs/research/phase-1-vishwas-agent-recovery.md): ARIA role + name → aria-label/<label> → visible
    text → CSS selector. Names match as substrings, so "Repository Name" finds "Repository Name *".
    A strategy counts only if it matches exactly ONE visible element. If role or text matched several,
    the optional vision locator picks the one Gemini points at. Vision never acts on an element that
    didn't match the planned role/name or text, and the action itself still goes through Playwright's
    actionability checks (no raw mouse clicks, no JS clicks).

    Failures come back as `ActionResult(ok=False)` with a typed error code; the executor never raises for a
    failed action. It does not decide whether an action is allowed: destructive actions must pass the
    policy layer before they reach `execute`.
    """

    def __init__(self, page: Page, vision: VisionLocator | None = None, *, settle_ms: int = 0) -> None:
        self._page = page
        self._vision = vision
        self._settle_ms = settle_ms
        """Wait after a navigate: on GitHub a button clicked before the page's scripts have loaded does
        nothing ("New label" opened no dialog, #89)."""
        self._last_filled: Locator | None = None
        """The field the last successful fill/select typed into: several identical buttons (Gitea's three
        "Update Settings") are told apart by which one belongs to that field's form (#83)."""

    async def execute(
        self, action: Action, target: Target | None = None, *, instruction: str | None = None
    ) -> ActionResult:
        """`instruction` (the step's instruction_text) helps the vision fallback tell candidates apart."""
        started_at = datetime.now(UTC)
        t0 = time.perf_counter()
        bbox: BoundingBox | None = None
        scroll: ScrollOffset | None = None
        locator: Locator | None = None
        strategy: LocatorStrategy | None = None
        context: ElementContext | None = None
        attempts: list[LLMAttempt] = []
        candidates: list[Candidate] = []
        error: ActionError | None = None
        try:
            _validate(action, target)
            if target is not None and (target.role or target.selector):
                locator, strategy = await self._resolve(target, instruction, attempts)
                context = await element_context(locator)
                bbox, scroll = await self._page_bbox(locator)
            await self._perform(action, locator)
            self._last_filled = locator if action.type in ("fill", "select") else self._last_filled
            if action.type == "navigate":
                self._last_filled = None
            if locator is None:
                scroll = await self._scroll()
        except _InvalidActionError as e:
            error = ActionError(code="invalid_action", message=str(e))
        except _UnresolvedTargetError as e:
            error = ActionError(code=e.code, message=str(e))
            if e.code in ("target_not_found", "ambiguous_target") and target is not None and target.role:
                candidates = await role_candidates(self._page, target.role)
        except PlaywrightTimeoutError as e:
            error = ActionError(code="timeout", message=_first_line(e))
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
            scroll=scroll,
            url_after=self.current_path(),
            strategy=strategy,
            context=context,
            llm_attempts=attempts,
            candidates=candidates,
            error=error,
        )

    def current_path(self) -> str:
        """The page's URL path (no scheme or host)."""
        return urlsplit(self._page.url).path or "/"

    def _strategies(self, target: Target) -> list[tuple[LocatorStrategy, Locator]]:
        page, name = self._page, target.name
        found: list[tuple[LocatorStrategy, Locator]] = []
        if target.role:
            # Roles come from ARIA snapshots / the LLM as plain strings; Playwright checks them at runtime.
            found.append(("role", page.get_by_role(target.role, name=name)))  # type: ignore[arg-type]
            loose = _quote_insensitive(name) if name else None
            if loose is not None:
                # An LLM often drops or changes the quotes inside a name: "Create new branch from main" for
                # Gitea's button `Create new branch from "main"` (#83). Same words, anything in between.
                found.append(("role", page.get_by_role(target.role, name=loose)))  # type: ignore[arg-type]
            if name:
                found += [("label", page.get_by_label(name)), ("text", page.get_by_text(name))]
        if target.selector:
            found.append(("selector", page.locator(target.selector)))
        return found

    async def _resolve(
        self, target: Target, instruction: str | None, attempts: list[LLMAttempt]
    ) -> tuple[Locator, LocatorStrategy]:
        strategies = self._strategies(target)
        # Wait (up to the action timeout) until ANY strategy shows something, then try them in order
        # without waiting again: a renamed element costs one timeout at most, not one per strategy.
        anything = strategies[0][1]
        for _, loc in strategies[1:]:
            anything = anything.or_(loc)
        try:
            await anything.filter(visible=True).first.wait_for(state="visible")
        except PlaywrightTimeoutError:
            hidden = any([await loc.count() > 0 for _, loc in strategies])
            code: ActionErrorCode = "timeout" if hidden else "target_not_found"
            raise _UnresolvedTargetError(code, f"no visible element for {_describe(target)}") from None

        several: list[Locator] = []
        for strategy, loc in strategies:
            visible = loc.filter(visible=True)
            count = await visible.count()
            if count == 1:
                return visible, strategy
            if count > 1 and strategy == "role" and not several:
                # Several elements contain the name: one named exactly so is the one meant. Decided here,
                # before the weaker strategies: the label "Leave a comment" also contains "Comment" (#100).
                exact = await self._pick_exact_name(target)
                if exact is not None:
                    return exact, "role"
            if count > 1 and strategy in ("role", "text"):
                several.append(visible)
        if not several:
            raise _UnresolvedTargetError("target_not_found", f"no visible element for {_describe(target)}")
        in_form = await self._pick_in_filled_form(several)
        if in_form is not None:
            return in_form, "form"
        picked = await self._pick_with_vision(target, instruction, several, attempts)
        if picked is None:
            raise _UnresolvedTargetError(
                "ambiguous_target", f"several elements match {_describe(target)} and none could be picked"
            )
        return picked, "vision"

    async def _pick_exact_name(self, target: Target) -> Locator | None:
        """The one visible element whose name is exactly the target's, when the substring match found several.
        Names match as substrings, so "Comment" also finds "Close with Comment"; both sit in the comment form,
        and the vision fallback once clicked the sidebar instead (#100)."""
        if not target.role or not target.name:
            return None
        exact = self._page.get_by_role(target.role, name=target.name, exact=True).filter(visible=True)  # type: ignore[arg-type]
        return exact if await exact.count() == 1 else None

    async def _pick_in_filled_form(self, several: list[Locator]) -> Locator | None:
        """The one candidate inside the form of the field filled just before, or None. Deterministic and free,
        so it goes before the vision fallback: "fill a field, then submit its form" is the usual flow."""
        if self._last_filled is None:
            return None
        try:
            form = await self._last_filled.evaluate_handle("e => e.closest('form')")
            if await form.evaluate("f => f === null"):
                return None
            for candidates in several:  # role matches first, then text matches
                hits = [
                    candidates.nth(i)
                    for i in range(await candidates.count())
                    if await candidates.nth(i).evaluate("(e, f) => f.contains(e)", form)
                ]
                if len(hits) == 1:
                    return hits[0]
        except PlaywrightError:
            return None  # the field is gone (another page): no form to go by
        return None

    async def _pick_with_vision(
        self, target: Target, instruction: str | None, several: list[Locator], attempts: list[LLMAttempt]
    ) -> Locator | None:
        """The one candidate whose box contains the point Gemini chose, or None."""
        if self._vision is None:
            return None
        result = await self._vision.point(self._page, target, instruction)
        attempts += result.attempts
        if result.point is None:
            return None
        x, y = result.point
        for candidates in several:  # role matches first, then text matches
            hits = []
            for i in range(await candidates.count()):
                box = await candidates.nth(i).bounding_box()  # viewport coordinates, like the screenshot
                if box and _contains(box, x, y):
                    hits.append(candidates.nth(i))
            if len(hits) == 1:
                return hits[0]
        return None

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
                if self._settle_ms:
                    await self._page.wait_for_timeout(self._settle_ms)
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

    async def _page_bbox(self, locator: Locator) -> tuple[BoundingBox | None, ScrollOffset]:
        # The action scrolls the element into view before acting. Doing it first means the scroll measured
        # here is the one the action (and the recording) happens at (phase-2-vishwas-coordinates.md).
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        scroll = await self._scroll()
        if box is None:
            return None, scroll
        # bounding_box() is relative to the viewport; the contract wants page coordinates.
        return (box["x"] + scroll.x, box["y"] + scroll.y, box["width"], box["height"]), scroll

    async def _scroll(self) -> ScrollOffset:
        x, y = await self._page.evaluate("[window.scrollX, window.scrollY]")
        return ScrollOffset(x=max(x, 0), y=max(y, 0))


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


def _quote_insensitive(name: str) -> re.Pattern[str] | None:
    """The name's words in order, with anything but letters and digits between them (quotes, typographic
    quotes, punctuation), case-insensitive. No literal quote characters: Playwright puts the regex into a
    selector string, and a quote inside it breaks that selector."""
    words = re.findall(r"\w+", name)
    if not words:
        return None
    return re.compile(r"\W*" + r"\W+".join(re.escape(w) for w in words), re.IGNORECASE)


def _contains(box: FloatRect, x: float, y: float) -> bool:
    return box["x"] <= x <= box["x"] + box["width"] and box["y"] <= y <= box["y"] + box["height"]


def _describe(target: Target) -> str:
    parts = [f"role={target.role}" if target.role else "", f"name={target.name!r}" if target.name else ""]
    parts.append(f"selector={target.selector!r}" if target.selector else "")
    return " ".join(p for p in parts if p)


def _first_line(e: Exception) -> str:
    return str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
