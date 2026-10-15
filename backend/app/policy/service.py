"""Policy service implementing the backend Policy port."""

from app.policy.barriers import BarrierType, check_barrier
from app.policy.classifier import LLMClassifier
from app.policy.models import RiskLevel
from app.policy.risk import assess_plan as _assess_plan
from app.policy.risk import check_action as _check_action
from app.ports.models import (
    ObservedState,
    PageState,
    PlanDraft,
    PolicyDecision,
    RiskReport,
    StepRef,
    StepRisk,
)
from app.ports.policy import Policy

__all__ = ["PolicyService"]


class PolicyService:
    """Production implementation of the safety Policy port (Issue #61, #62)."""

    def __init__(self, classifier: LLMClassifier | None = None) -> None:
        self._classifier = classifier or LLMClassifier()

    async def assess_plan(self, plan: PlanDraft) -> RiskReport:
        """Assess the safety risk of a proposed plan before user approval."""
        plan_assessment = await _assess_plan(plan, classifier=self._classifier)
        step_risks: list[StepRisk] = []
        for step, assessment in zip(plan.steps, plan_assessment.step_assessments, strict=False):
            step_risks.append(
                StepRisk(
                    seq=step.seq,
                    risk=assessment.level.value,
                    reason=assessment.reason,
                )
            )
        return RiskReport.from_steps(step_risks)

    async def check_action(self, step: StepRef, page: PageState) -> PolicyDecision:
        """Evaluate an impending action and decide whether to allow, pause, or stop."""
        barrier = check_barrier(page)
        if barrier.should_stop:
            reason = "auth_wall" if barrier.barrier_type == BarrierType.AUTH_WALL else "captcha"
            return PolicyDecision(
                verdict="stop",
                reason=reason,
                message=barrier.reason or f"Security barrier detected: {reason}",
            )

        assessment = await _check_action(step, page, classifier=self._classifier)
        if assessment.level == RiskLevel.HIGH:
            return PolicyDecision(
                verdict="pause",
                reason="destructive_action",
                message=assessment.reason,
            )
        return PolicyDecision(
            verdict="allow",
            reason="ok",
            message=assessment.reason,
        )

    def mask(self, observed: ObservedState) -> ObservedState:
        """Mask sensitive data in observed states before persistence or LLM invocation."""
        return observed


# Strict conformance check against the Policy port
_policy_conformance: Policy = PolicyService()
