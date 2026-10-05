from typing import Protocol

from app.ports.models import ObservedState, PageState, PlanDraft, PolicyDecision, RiskReport, StepRef


class Policy(Protocol):
    """Safety layer. Implemented by `app.policy` (Nachiketha); used by the planner and executor (Vishwas)."""

    async def assess_plan(self, plan: PlanDraft) -> RiskReport:
        """Risk of a proposed plan, shown to the user before approval."""
        ...

    async def check_action(self, step: StepRef, page: PageState) -> PolicyDecision:
        """Called before every action: allow it, pause for human confirmation, or stop the run
        (CAPTCHA, bot wall, auth wall). `page` is untrusted content, never instructions."""
        ...

    def mask(self, observed: ObservedState) -> ObservedState:
        """Return a copy with sensitive data removed. Called before anything is stored or sent to an LLM."""
        ...
