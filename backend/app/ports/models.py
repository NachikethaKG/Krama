"""Value types used in port signatures.

`Action`, `Target`, `ActionType` and `Risk` are the generated contract types (app.contracts_gen), re-exported
here so callers pass contract objects straight through a port. The models below have no contract schema of the
same shape and stay port-specific:

- `StepRef` is the part of a contract `PlannedStep` an Observer needs (no expected_state or risk).
- `PlanDraft`, `PageState`, `RiskReport`, `PolicyDecision`: inputs/outputs of the Policy port only.
- `ObservedState` is stricter than the contract `step_schema.ObservedState` (title and captured_at are always
  set by a capture). Convert at the API boundary.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts_gen.common_schema import Action, ActionType, Risk, Target

__all__ = [
    "Action",
    "ActionType",
    "DecisionReason",
    "ObservedState",
    "PageState",
    "PlanDraft",
    "PolicyDecision",
    "RecordingRef",
    "Risk",
    "RiskReport",
    "StepRef",
    "StepRisk",
    "Target",
    "Verdict",
]

Verdict = Literal["allow", "pause", "stop"]
# Same values as the `run.paused` event's `reason` in docs/api-contract.md, plus the non-pausing cases.
DecisionReason = Literal[
    "ok", "destructive_action", "captcha", "auth_wall", "rate_limited", "sensitive_data", "prompt_injection"
]

_RISK_ORDER: dict[Risk, int] = {"low": 0, "medium": 1, "high": 2}


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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
