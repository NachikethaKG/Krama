"""General policy step evaluator integrating GitHub danger-zone rules."""

from __future__ import annotations

from typing import Any

from app.policy.models import RiskLevel, StepRiskAssessment
from app.policy.rules_github import evaluate_github_danger_zone

__all__ = [
    "PolicyEvaluator",
    "evaluate_step",
]


def evaluate_step(
    action: Any = None,
    context: Any = None,
    *,
    url: str | None = None,
    target_selector: str | None = None,
    action_text: str | None = None,
) -> StepRiskAssessment:
    """Evaluate an impending step against GitHub danger-zone rules and general policy.

    If the target URL matches github.com, invokes evaluate_github_danger_zone before
    proceeding to standard evaluation.
    """
    clean_url = ""
    if url:
        clean_url = url
    elif hasattr(context, "url"):
        clean_url = str(getattr(context, "url", "") or "")
    elif isinstance(context, dict):
        clean_url = str(context.get("url", "") or "")
    elif isinstance(context, str):
        clean_url = context

    # Extract target text and selector from action if not explicitly passed
    text = action_text
    selector = target_selector
    if not text and isinstance(action, str):
        text = action
    elif hasattr(action, "target") and action.target is not None:
        target = action.target
        if not text:
            text = str(getattr(target, "name", "") or "")
        if not selector:
            selector = str(getattr(target, "selector", "") or getattr(target, "role", "") or "")
    if not text and hasattr(action, "action") and action.action is not None:
        action_inner = action.action
        if hasattr(action_inner, "target") and action_inner.target is not None:
            t = action_inner.target
            if not text:
                text = str(getattr(t, "name", "") or "")
            if not selector:
                selector = str(getattr(t, "selector", "") or getattr(t, "role", "") or "")

    # 1. GitHub danger-zone rules when targeting github.com
    if "github.com" in clean_url.lower():
        gh_verdict = evaluate_github_danger_zone(
            url=clean_url,
            target_selector=selector,
            action_text=text,
        )
        if gh_verdict.risk_level == RiskLevel.HIGH:
            return gh_verdict

    return StepRiskAssessment(
        risk_level=RiskLevel.LOW,
        reason="Action evaluated as safe",
        requires_confirmation=False,
    )


class PolicyEvaluator:
    """Evaluator class for assessing step-level safety."""

    @staticmethod
    def evaluate(
        action: Any = None,
        context: Any = None,
        *,
        url: str | None = None,
        target_selector: str | None = None,
        action_text: str | None = None,
    ) -> StepRiskAssessment:
        return evaluate_step(
            action,
            context,
            url=url,
            target_selector=target_selector,
            action_text=action_text,
        )
