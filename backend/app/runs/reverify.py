"""Re-verification (#77): replay a stored workflow's steps as an approved plan, without the planner.

The run goes through the normal executor (policy, observer, verifier), with `kind="reverify"`: it never
replans or pauses for a human, it stops at the first step that no longer works, and it stores no new
workflow (docs/research/phase-2-vishwas-reverify.md).
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.healer import HealOutcome
from app.agent.runlog import MASK
from app.contracts_gen.plan_schema import PlannedStep
from app.db import PlanRow, RunRow, WorkflowRow, WorkflowStepRow
from app.runs.steps import StepOutcome
from app.targets import Reset, ResetError

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


async def create_reverify_run(
    sessions: async_sessionmaker[AsyncSession], workflow_id: UUID, reset: Reset | None
) -> UUID:
    """Queue a reverify run of the workflow's current steps (#77): check they can be replayed, undo what the
    workflow creates (`reset`) so the replay starts where the recorded run did, then store the approved plan
    and the queued run. Used by POST /workflows/{id}/reverify and by scheduled validation (#110).

    Raises LookupError for an unknown workflow and ReverifyRefusedError (`high_risk_step`,
    `secret_not_stored`, `reset_failed`) for one that can't be replayed."""
    async with sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        if workflow is None:
            raise LookupError(str(workflow_id))
        steps = list(workflow.steps)
        task_id, title = workflow.task_id, workflow.title
    check_replayable(steps)
    if reset is not None:
        stored = [{"seq": st.seq, "action": st.action, "target": st.target, "before_state": st.before_state}
                  for st in steps]  # fmt: skip
        try:
            await reset(stored)
        except ResetError as e:
            raise ReverifyRefusedError("reset_failed", f"The target couldn't be reset: {e}") from None
    async with sessions.begin() as s:
        plan = PlanRow(
            task_id=task_id,
            status="approved",
            risk=plan_risk(steps),
            expected_result=title,
            steps=plan_steps(steps),
            approved_at=datetime.now(UTC),
        )
        s.add(plan)
        await s.flush()
        run = RunRow(
            plan_id=plan.id, plan_revision=1, status="queued", kind="reverify", source_workflow_id=workflow_id
        )
        s.add(run)
        await s.flush()
        return run.id


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
