"""One planned step: observe, act, observe, then re-verify until the expected state holds or time runs out.

Shared by `krama run` (runner.py) and the background executor (executor.py). If the action succeeded but
verification failed, the action is never repeated just to re-verify
(docs/research/phase-1-vishwas-agent-recovery.md). The state before the action is captured too: for a click,
something that was already true before can't prove the click worked (phase-1-together-verified-definition.md).
"""

import asyncio
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from playwright.async_api import Page, Request, Response

from app.agent import ActionExecutor, ActionResult
from app.contracts_gen.plan_schema import PlannedStep
from app.ports.models import ObservedState, StepRef
from app.ports.observer import Observer
from app.verifier import NetworkCall, StepEvidence, StepVerifier, VerificationOutcome

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
) -> StepOutcome:
    ref = StepRef(
        seq=step.seq, action=step.action, target=step.target, instruction_text=step.instruction_text
    )
    before = await observer.capture(page, ref)
    with _NetworkRecorder(page) as network:
        result = await executor.execute(step.action, step.target, instruction=step.instruction_text)
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
            if outcome.verification.result == "skipped":
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
