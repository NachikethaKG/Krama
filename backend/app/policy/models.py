from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ActionContext",
    "BarrierType",
    "BarrierVerdict",
    "PlanRiskAssessment",
    "RiskAssessment",
    "RiskLevel",
    "max_risk_level",
]


class BarrierType(StrEnum):
    """Types of anti-bot, access restriction, or rate limit barriers."""

    # Generic & Cloudflare (Phase 1)
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    RECAPTCHA = "recaptcha"
    HCAPTCHA = "hcaptcha"
    AUTH_WALL = "auth_wall"

    # GitHub-specific (Phase 3)
    GITHUB_RATE_LIMIT = "github_rate_limit"
    GITHUB_ABUSE_PAGE = "github_abuse_page"
    GITHUB_CHALLENGE = "github_challenge"


class BarrierVerdict(BaseModel):
    """Structured verdict from barrier detection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    should_stop: bool
    barrier_type: BarrierType | None = None
    reason: str | None = None


class RiskLevel(StrEnum):
    """Risk severity assigned to an action or plan."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_LEVEL_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}


def max_risk_level(levels: Iterable[RiskLevel]) -> RiskLevel:
    """Return the highest risk level from an iterable, defaulting to LOW."""
    return max(levels, key=_LEVEL_ORDER.__getitem__, default=RiskLevel.LOW)


class RiskAssessment(BaseModel):
    """Structured assessment of an action's or plan's risk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: RiskLevel
    reason: str
    flagged_by: str  # "denylist", "llm_classifier", "fallback_safe", "fast_path"
    confidence: float = 1.0
    matched_rule: str | None = None


class PlanRiskAssessment(RiskAssessment):
    """Assessment of a full plan with per-step assessments."""

    step_assessments: list[RiskAssessment] = Field(default_factory=list)


class ActionContext(BaseModel):
    """Context surrounding an action being evaluated by the policy."""

    model_config = ConfigDict(extra="allow", frozen=True)

    url: str = ""
    title: str = ""
    aria_excerpt: str = ""
    previous_step: str | None = None
    dialog_text: str | None = None
