"""Re-verification (#77): replay a stored workflow's steps as an approved plan, without the planner.

The run goes through the normal executor (policy, observer, verifier), with `kind="reverify"`: it never
replans or pauses for a human, it stops at the first step that no longer works, and it stores no new
workflow (docs/research/phase-2-vishwas-reverify.md).
"""

from collections.abc import Sequence
from typing import Any

from app.agent.healer import HealOutcome
from app.agent.runlog import MASK
from app.contracts_gen.plan_schema import PlannedStep
from app.db import WorkflowStepRow
from app.runs.steps import StepOutcome

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


class ReverifyRefusedError(Exception):
    """The workflow can't be replayed safely or meaningfully. `reason` goes in the 409's details."""

    def __init__(self, reason: str, message: str, step_seq: int | None = None) -> None:
        super().__init__(message)
        self.reason = reason
        self.step_seq = step_seq


def check_replayable(steps: Sequence[WorkflowStepRow]) -> None:
    """Raise ReverifyRefusedError for a workflow that a headless replay must not run."""
    if not steps:
        raise ReverifyRefusedError("no_steps", "The workflow has no steps to replay")
    for step in steps:
        if step.risk == "high":
            # Nobody watches a reverify, so a destructive step could never be confirmed (decision for #77).
            raise ReverifyRefusedError(
                "high_risk_step",
                f"Step {step.seq} is high risk; it is never replayed without a human",
                step.seq,
            )
        if step.sensitive or (step.action or {}).get("value") == MASK:
            raise ReverifyRefusedError(
                "secret_not_stored", f"Step {step.seq} typed a secret, and secrets are never stored", step.seq
            )


def plan_steps(steps: Sequence[WorkflowStepRow]) -> list[dict[str, Any]]:
    """The stored steps as the plan's PlannedStep documents (the run executes exactly these)."""
    planned = []
    for step in sorted(steps, key=lambda s: s.seq):
        target = {k: v for k, v in (step.target or {}).items() if k in ("role", "name", "selector") and v}
        planned.append(
            {
                "seq": step.seq,
                "action": step.action,
                "target": target,
                "instruction_text": step.instruction_text,
                "expected_state": step.expected_state,
                "risk": step.risk,
            }
        )
    return planned


def plan_risk(steps: Sequence[WorkflowStepRow]) -> str:
    return max((s.risk for s in steps), key=_RISK_ORDER.__getitem__, default="low")


def failure_details(step: PlannedStep, out: StepOutcome, heal: HealOutcome | None = None) -> dict[str, Any]:
    """Evidence for validation (#109): what the step looked for, and what the page offered (a locator miss) or
    which expected-state checks failed (a state mismatch). Page text in it is untrusted data."""
    details: dict[str, Any] = {
        "target": step.target.model_dump(exclude_none=True),
        "url": out.result.url_after,
    }
    if out.result.error is not None:
        details["error_code"] = out.result.error.code
    if out.result.candidates:
        details["candidates"] = [c.model_dump(mode="json", exclude_none=True) for c in out.result.candidates]
    if heal is not None:
        # Why self-healing (#112) didn't fix it, and how the candidates scored: for the review queue.
        details["heal"] = {
            "reason": heal.reason,
            "scores": [{"name": s.candidate.name, "score": s.score} for s in heal.ranked[:5]],
        }
    if out.verification is not None and out.result.ok:
        details["failed_checks"] = [
            {"kind": c.kind, "expected": c.expected, "detail": c.detail} for c in out.verification.failures()
        ]
    return details
