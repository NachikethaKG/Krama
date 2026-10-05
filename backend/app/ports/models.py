"""Value types used in port signatures.

PROVISIONAL: these exist because the generated contract models (#15, #16) don't exist yet.
When they do, every model here that overlaps a contract schema (StepRef, PlanDraft, ObservedState)
is replaced by an import from `app.contracts_gen`. Keep field names and shapes aligned with
docs/api-contract.md and docs/research/phase-f-together-gitea-create-repo-walkthrough.md.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionType = Literal["click", "fill", "select", "navigate", "press", "wait"]
Risk = Literal["low", "medium", "high"]
Verdict = Literal["allow", "pause", "stop"]
# Same values as the `run.paused` event's `reason` in docs/api-contract.md, plus the non-pausing cases.
DecisionReason = Literal[
    "ok", "destructive_action", "captcha", "auth_wall", "rate_limited", "sensitive_data", "prompt_injection"
]

_RISK_ORDER: dict[Risk, int] = {"low": 0, "medium": 1, "high": 2}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Action(_Model):
    type: ActionType
    value: str | None = None


class Target(_Model):
    """How to find the element: ARIA role + accessible name first, CSS selector as a fallback."""

    role: str | None = None
    name: str | None = None
    selector: str | None = None


class StepRef(_Model):
    """One planned step, as the agent is about to execute it."""

    seq: int = Field(ge=1)
    action: Action
    target: Target
    instruction_text: str = Field(min_length=1)


class PlanDraft(_Model):
    """A proposed plan before approval."""

    task: str = Field(min_length=1)
    steps: list[StepRef]


class PageState(_Model):
    """What the page looks like right now. Everything here is UNTRUSTED page content, never instructions."""

    url: str = Field(description="Path only, e.g. /repo/create (no scheme or host)")
    title: str
    aria_excerpt: str = ""


class ObservedState(_Model):
    """What the Observer captured after a step."""

    url: str = Field(description="Path only, e.g. /repo/create (no scheme or host)")
    title: str
    headings: list[str] = []
    aria_excerpt: str = ""
    screenshot_path: str | None = None
    captured_at: datetime


class RecordingRef(_Model):
    """Where a finished rrweb recording was stored."""

    path: str
    event_count: int = Field(ge=0)
    started_at: datetime
    ended_at: datetime


class StepRisk(_Model):
    seq: int = Field(ge=1)
    risk: Risk
    reason: str


class RiskReport(_Model):
    """Policy's assessment of a whole plan, shown to the user before approval."""

    level: Risk
    steps: list[StepRisk] = []

    @classmethod
    def from_steps(cls, steps: list[StepRisk]) -> "RiskReport":
        level: Risk = max((s.risk for s in steps), key=_RISK_ORDER.__getitem__, default="low")
        return cls(level=level, steps=steps)


class PolicyDecision(_Model):
    """Whether the agent may perform the next action."""

    verdict: Verdict
    reason: DecisionReason = "ok"
    message: str = ""
