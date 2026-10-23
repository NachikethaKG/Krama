"""Policy module: risk classification, safety guardrails, and action verification."""

from app.policy.barriers import BarrierCheckResult, BarrierType, check_barrier
from app.policy.barriers_github import evaluate_github_barriers
from app.policy.classifier import LLMClassifier
from app.policy.denylist import DENYLIST_KEYWORDS
from app.policy.evaluator import PolicyEvaluator, evaluate_step
from app.policy.masking import is_sensitive_key, mask_dict, mask_prompt, mask_text
from app.policy.models import (
    ActionContext,
    BarrierVerdict,
    PlanRiskAssessment,
    RiskAssessment,
    RiskLevel,
    StepRiskAssessment,
    max_risk_level,
)
from app.policy.risk import assess_plan, check_action
from app.policy.rules_github import (
    BRANCH_DELETE_SELECTOR_RE,
    GITHUB_DESTRUCTIVE_PHRASES,
    evaluate_github_danger_zone,
)
from app.policy.service import PolicyService

__all__ = [
    "BRANCH_DELETE_SELECTOR_RE",
    "DENYLIST_KEYWORDS",
    "GITHUB_DESTRUCTIVE_PHRASES",
    "ActionContext",
    "BarrierCheckResult",
    "BarrierType",
    "BarrierVerdict",
    "LLMClassifier",
    "PlanRiskAssessment",
    "PolicyEvaluator",
    "PolicyService",
    "RiskAssessment",
    "RiskLevel",
    "StepRiskAssessment",
    "assess_plan",
    "check_action",
    "check_barrier",
    "evaluate_github_barriers",
    "evaluate_github_danger_zone",
    "evaluate_step",
    "is_sensitive_key",
    "mask_dict",
    "mask_prompt",
    "mask_text",
    "max_risk_level",
]
