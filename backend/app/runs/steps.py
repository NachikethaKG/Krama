"""One planned step: observe, act, observe, then re-verify until the expected state holds or time runs out.

Shared by `krama run` (runner.py) and the background executor (executor.py). If the action succeeded but
verification failed, the action is never repeated just to re-verify
(docs/research/phase-1-vishwas-agent-recovery.md). The state before the action is captured too: for a click,
something that was already true before can't prove the click worked (phase-1-together-verified-definition.md).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

from playwright.async_api import Page, Request, Response

from app.agent import ActionExecutor, ActionResult
from app.contracts_gen.common_schema import ExpectedState
from app.contracts_gen.plan_schema import PlannedStep
from app.ports.models import ObservedState, StepRef
from app.ports.observer import Observer
from app.verifier import NetworkCall, RuleVerifier, StepEvidence, StepVerifier, VerificationOutcome
from app.verifier.change import observed_change

_DATA_REQUESTS = frozenset({"document", "xhr", "fetch"})


@dataclass(frozen=True)
class StepOutcome:
    result: ActionResult
    before: ObservedState | None
    observed: ObservedState
    verification: VerificationOutcome | None
    """None if the action itself failed (nothing to verify)."""
    verify_attempts: int
    network: list[NetworkCall] = field(default_factory=list)
    focus_screenshot: str | None = None
    """Artifact key of the page right before the action, with the target scrolled into view: where `bbox` and
    `scroll` were measured, and what a click step's video scene shows (#388). None without a target."""
    by_hand_pending: bool = False
    """The owner took over at the pause before this step's action: nothing ran yet (ADR 0008)."""

    @classmethod
    def pending_by_hand(cls, before: ObservedState) -> "StepOutcome":
        result = ActionResult(
            action="wait", ok=True, started_at=datetime.now(UTC), duration_ms=0, url_after=before.url
        )
        return cls(result=result, before=before, observed=before, verification=None, verify_attempts=0,
                   by_hand_pending=True)  # fmt: skip

    @property
    def verified(self) -> bool:
        return self.result.ok and self.verification is not None and self.verification.verified

    @property
    def unclear(self) -> bool:
        """The action ran and nothing failed, but nothing proved it worked either (`skipped`)."""
        return (
            self.result.ok
            and self.verification is not None
            and self.verification.verification.result == "skipped"
        )


async def act_and_verify(
    step: PlannedStep,
    executor: ActionExecutor,
    observer: Observer,
    verifier: StepVerifier,
    page: Page,
    *,
    verify_timeout_s: float,
    verify_interval_s: float,
    before: ObservedState | None = None,
    focus_shot: Callable[[], Awaitable[str | None]] | None = None,
    vision: bool = True,
    act: bool = True,
) -> StepOutcome:
    """`before`: the page right before the action, if the caller already captured it (policy check).
    `focus_shot`: stores a screenshot once the target is scrolled into view and returns its key (#388).
    `vision`: False never asks the vision judge; an undecided step stays `skipped` (a do-it run, P10).
    `act`: False only checks the step's expected state on the page as it is: the owner did it by hand in a
    takeover (ADR 0008)."""
    ref = step_ref(step)
    if before is None:
        before = await observer.capture(page, ref)
    focus: list[str] = []

    async def on_ready() -> None:
        if focus_shot is not None and (key := await focus_shot()):
            focus.append(key)

    with _NetworkRecorder(page) as network:
        if act:
            result = await executor.execute(
                step.action, step.target, instruction=step.instruction_text, on_ready=on_ready
            )
        else:
            result = ActionResult(
                action=step.action.type, ok=True, started_at=datetime.now(UTC), duration_ms=0,
                url_after=urlsplit(page.url).path or "/",
            )  # fmt: skip
        observed = await observer.capture(page, ref)
        outcome: VerificationOutcome | None = None
        attempts = 0
        if result.ok:
            deadline = time.perf_counter() + verify_timeout_s
            while True:
                attempts += 1
                outcome = await verifier.verify(
                    step.expected_state, _evidence(step, before, observed, network)
                )
                # Keep looking after a failed check too: a page may still be navigating or rendering.
                if outcome.verified or time.perf_counter() >= deadline:
                    break
                await asyncio.sleep(verify_interval_s)
                observed = await observer.capture(page, ref)
            if vision and outcome.verification.result == "skipped":
                # The cheap layers couldn't decide: one look with vision, as evidence for the human.
                evidence = _evidence(step, before, observed, network)
                outcome = await verifier.verify(step.expected_state, evidence, page=page, use_vision=True)
    return StepOutcome(
        result=result,
        before=before,
        observed=observed,
        verification=outcome,
        verify_attempts=attempts,
        network=list(network.calls),
        focus_screenshot=focus[0] if focus else None,
    )


async def act_and_record(
    step: PlannedStep,
    executor: ActionExecutor,
    observer: Observer,
    verifier: StepVerifier,
    page: Page,
    *,
    before: ObservedState,
    change_timeout_s: float,
    check_interval_s: float,
    focus_shot: Callable[[], Awaitable[str | None]] | None = None,
) -> tuple[PlannedStep, StepOutcome]:
    """Step mode (ADR 0011, #469): act, then watch the page until the action visibly changed something, keep
    that change as the step's expected state. The step is then verified against it, as a replay will be.

    Nothing visible within `change_timeout_s`: the step comes back with its empty expected state and an
    outcome that is `unclear` (skipped), never `verified`."""
    ref = step_ref(step)
    focus: list[str] = []

    async def on_ready() -> None:
        if focus_shot is not None and (key := await focus_shot()):
            focus.append(key)

    with _NetworkRecorder(page) as network:
        result = await executor.execute(
            step.action, step.target, instruction=step.instruction_text, on_ready=on_ready
        )
        observed = await observer.capture(page, ref)
        recorded = step
        outcome: VerificationOutcome | None = None
        attempts = 0
        if result.ok:
            deadline = time.perf_counter() + change_timeout_s
            while True:
                attempts += 1
                change = observed_change(before, observed, step.action, step.target)
                if change is not None:
                    recorded = step.model_copy(update={"expected_state": change})
                    outcome = await verifier.verify(change, _evidence(recorded, before, observed, network))
                    if outcome.verified:
                        break
                if time.perf_counter() >= deadline:
                    break
                await asyncio.sleep(check_interval_s)
                observed = await observer.capture(page, ref)
            if outcome is None:
                outcome = await verifier.verify(
                    step.expected_state, _evidence(step, before, observed, network)
                )
    return recorded, StepOutcome(
        result=result,
        before=before,
        observed=observed,
        verification=outcome,
        verify_attempts=attempts,
        network=list(network.calls),
        focus_screenshot=focus[0] if focus else None,
    )


def already_done(step: PlannedStep, out: StepOutcome) -> bool:
    """A replayed step that has nothing left to do (#482): it closed a one-time popup (Habitica's "New Stuff
    by Bailey", a daily "Check-In Prize", a tip), and the popup isn't there now. True only when all hold:

    - its element isn't on the page (not found; an ambiguous element is still there, so it doesn't count);
    - its expected state is only "these are gone" (`absent`), plus at most other dialogs that appeared
      (closing one popup can open the next: "You have received Standard Backgrounds");
    - each of those is gone on the page as it is: the closed popup, and the dialogs it led to.

    A step expected to reach a URL, fill a field, or show anything but a dialog is never "already done"."""
    error = out.result.error
    expected = step.expected_state
    if error is None or error.code != "target_not_found" or not expected.absent:
        return False
    if expected.model_dump(exclude_none=True, exclude={"absent", "visible"}):
        return False
    chained = expected.visible or []
    if any(ref.role not in _DIALOGS for ref in chained):
        return False
    gone = ExpectedState(absent=[*expected.absent, *chained])
    return RuleVerifier().verify(gone, out.observed).verified


_DIALOGS = frozenset({"dialog", "alertdialog"})


def step_ref(step: PlannedStep) -> StepRef:
    return StepRef(
        seq=step.seq, action=step.action, target=step.target, instruction_text=step.instruction_text
    )


def _evidence(
    step: PlannedStep, before: ObservedState, after: ObservedState, network: "_NetworkRecorder"
) -> StepEvidence:
    return StepEvidence(
        action=step.action,
        target=step.target,
        instruction_text=step.instruction_text,
        before=before,
        after=after,
        network=list(network.calls),
    )


class _NetworkRecorder:
    """Same-origin requests that could change data (not GET) while the step runs: a form POST answered with
    2xx/3xx is evidence that a submit worked; 4xx/5xx or no answer is evidence that it didn't."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._origin = urlsplit(page.url).netloc
        self.calls: list[NetworkCall] = []

    def __enter__(self) -> "_NetworkRecorder":
        self._page.on("response", self._on_response)
        self._page.on("requestfailed", self._on_failed)
        return self

    def __exit__(self, *exc: object) -> None:
        self._page.remove_listener("response", self._on_response)
        self._page.remove_listener("requestfailed", self._on_failed)

    def _keep(self, request: Request) -> bool:
        url = urlsplit(request.url)
        return (
            request.method != "GET" and request.resource_type in _DATA_REQUESTS and url.netloc == self._origin
        )

    def _on_response(self, response: Response) -> None:
        request = response.request
        if self._keep(request):
            self.calls.append(_call(request, response.status))

    def _on_failed(self, request: Request) -> None:
        if self._keep(request):
            self.calls.append(_call(request, None))


def _call(request: Request, status: int | None) -> NetworkCall:
    return NetworkCall(
        method=request.method,
        path=urlsplit(request.url).path or "/",
        status=status,
        resource_type=request.resource_type,
    )
