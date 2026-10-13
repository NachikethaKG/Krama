"""One planned step: act, observe, then re-verify until the expected state holds or time runs out.

Shared by `krama run` (runner.py) and the background executor (executor.py). If the action succeeded but
verification failed, the action is never repeated just to re-verify
(docs/research/phase-1-vishwas-agent-recovery.md).
"""

import asyncio
import time
from dataclasses import dataclass

from playwright.async_api import Page

from app.agent import ActionExecutor, ActionResult
from app.contracts_gen.plan_schema import PlannedStep
from app.ports.models import ObservedState, StepRef
from app.ports.observer import Observer
from app.verifier import VerificationOutcome, Verifier


@dataclass(frozen=True)
class StepOutcome:
    result: ActionResult
    observed: ObservedState
    verification: VerificationOutcome | None
    """None if the action itself failed (nothing to verify)."""
    verify_attempts: int

    @property
    def verified(self) -> bool:
        return self.result.ok and self.verification is not None and self.verification.verified


async def act_and_verify(
    step: PlannedStep,
    executor: ActionExecutor,
    observer: Observer,
    verifier: Verifier,
    page: Page,
    *,
    verify_timeout_s: float,
    verify_interval_s: float,
) -> StepOutcome:
    ref = StepRef(
        seq=step.seq, action=step.action, target=step.target, instruction_text=step.instruction_text
    )
    result = await executor.execute(step.action, step.target, instruction=step.instruction_text)
    observed = await observer.capture(page, ref)
    outcome: VerificationOutcome | None = None
    attempts = 0
    if result.ok:
        deadline = time.perf_counter() + verify_timeout_s
        while True:
            attempts += 1
            outcome = verifier.verify(step.expected_state, observed)
            if outcome.verified or time.perf_counter() >= deadline:
                break
            await asyncio.sleep(verify_interval_s)
            observed = await observer.capture(page, ref)
    return StepOutcome(result=result, observed=observed, verification=outcome, verify_attempts=attempts)
