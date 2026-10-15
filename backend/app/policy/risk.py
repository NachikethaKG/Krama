"""Core risk assessment engine for browser actions and plans."""

from collections.abc import Sequence
from typing import Any

from app.policy.classifier import LLMClassifier
from app.policy.denylist import (
    check_gitea_baseline,
    is_ambiguous,
    is_benign,
    match_denylist_keywords,
)
from app.policy.models import (
    ActionContext,
    PlanRiskAssessment,
    RiskAssessment,
    RiskLevel,
    max_risk_level,
)

__all__ = ["assess_plan", "check_action"]


def _normalize_context(context: Any) -> ActionContext:
    if context is None:
        return ActionContext()
    if isinstance(context, ActionContext):
        return context
    if isinstance(context, str):
        return ActionContext(url=context)
    if hasattr(context, "url") and hasattr(context, "title"):
        return ActionContext(
            url=str(context.url or ""),
            title=str(context.title or ""),
            aria_excerpt=str(getattr(context, "aria_excerpt", "") or ""),
        )
    if isinstance(context, dict):
        return ActionContext(
            url=str(context.get("url", "")),
            title=str(context.get("title", "")),
            aria_excerpt=str(context.get("aria_excerpt", "")),
            dialog_text=str(context.get("dialog_text")) if context.get("dialog_text") else None,
            previous_step=str(context.get("previous_step")) if context.get("previous_step") else None,
        )
    return ActionContext()


def _normalize_action(action: Any) -> tuple[str, str, str, str, str]:
    """Extract (name, role, action_type, action_value, instruction) from arbitrary action inputs."""
    name = ""
    role = ""
    action_type = "click"
    action_value = ""
    instruction = ""

    if isinstance(action, str):
        name = action
        instruction = action
        return name, role, action_type, action_value, instruction

    # StepRef, PlannedStep, or similar objects
    if hasattr(action, "target") and action.target is not None:
        target = action.target
        name = str(getattr(target, "name", "") or "")
        role = str(getattr(target, "role", "") or "")
    if hasattr(action, "action") and action.action is not None:
        act = action.action
        action_type = str(getattr(act, "type", "click"))
        action_value = str(getattr(act, "value", "") or "")
    if hasattr(action, "instruction_text"):
        instruction = str(action.instruction_text or "")

    # If action was a dict
    if isinstance(action, dict):
        if "name" in action:
            name = str(action["name"])
        elif "target" in action and isinstance(action["target"], dict):
            name = str(action["target"].get("name", ""))
            role = str(action["target"].get("role", ""))

        if "role" in action:
            role = str(action["role"])

        if "instruction_text" in action:
            instruction = str(action["instruction_text"])
        elif "instruction" in action:
            instruction = str(action["instruction"])

        if "action" in action and isinstance(action["action"], dict):
            action_type = str(action["action"].get("type", "click"))
            action_value = str(action["action"].get("value", "") or "")
        elif "type" in action:
            action_type = str(action["type"])
            action_value = str(action.get("value", "") or "")

    return name, role, action_type, action_value, instruction


async def check_action(
    action: Any,
    context: Any = None,
    *,
    classifier: LLMClassifier | None = None,
) -> RiskAssessment:
    """Classify a single action into low, medium, or high risk.

    Utilizes:
    1. Benign fast-path to eliminate false positives on benign controls.
    2. Deterministic baseline rules matching destructive Gitea actions.
    3. LLM classifier fallback for ambiguous phrases/contexts (e.g. 'delete draft').
    4. Deterministic keyword denylist covering delete, purchase, transfer, publish, send, reset, security.
    """
    name, role, action_type, action_value, instruction = _normalize_action(action)
    ctx = _normalize_context(context)

    # Text summary of what is happening
    full_text = " ".join(part for part in (name, instruction, action_value) if part).strip()
    if not full_text:
        full_text = name or instruction or action_type

    # 1. Benign fast-path
    benign_match = is_benign(name or full_text, role, ctx.url)
    if benign_match:
        return benign_match

    # 2. Gitea destructive baseline rules
    baseline_match = check_gitea_baseline(name or full_text, role, ctx.url, ctx)
    if baseline_match:
        return baseline_match

    # 3. Disambiguation for ambiguous context (e.g. 'delete draft' vs 'delete repository')
    if is_ambiguous(full_text, ctx):
        clf = classifier or LLMClassifier()
        return await clf.classify(full_text, ctx)

    # 4. Deterministic denylist check
    matched_kws = match_denylist_keywords(full_text)
    if matched_kws:
        kw = matched_kws[0]
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason=f"Action matches denylist keyword: '{kw}' ({full_text})",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule=f"denylist_keyword_{kw}",
        )

    # 5. Default benign action
    return RiskAssessment(
        level=RiskLevel.LOW,
        reason=f"Benign interaction: '{full_text}'",
        flagged_by="fast_path",
        confidence=1.0,
        matched_rule="default_low",
    )


async def assess_plan(
    plan: Any,
    *,
    classifier: LLMClassifier | None = None,
) -> PlanRiskAssessment:
    """Classify an entire plan by assessing all steps and aggregating the risk."""
    steps: Sequence[Any] = ()

    if isinstance(plan, str):
        # Single string task or instruction
        step_assessment = await check_action(plan, classifier=classifier)
        return PlanRiskAssessment(
            level=step_assessment.level,
            reason=step_assessment.reason,
            flagged_by=step_assessment.flagged_by,
            confidence=step_assessment.confidence,
            matched_rule=step_assessment.matched_rule,
            step_assessments=[step_assessment],
        )

    if hasattr(plan, "steps"):
        steps = plan.steps
    elif isinstance(plan, dict) and "steps" in plan:
        steps = plan["steps"]
    elif isinstance(plan, Sequence):
        steps = plan

    if not steps:
        task_desc = plan.task if hasattr(plan, "task") else str(plan)
        if task_desc and isinstance(task_desc, str) and task_desc != str(plan):
            step_assessment = await check_action(task_desc, classifier=classifier)
            return PlanRiskAssessment(
                level=step_assessment.level,
                reason=step_assessment.reason,
                flagged_by=step_assessment.flagged_by,
                confidence=step_assessment.confidence,
                matched_rule=step_assessment.matched_rule,
                step_assessments=[step_assessment],
            )
        return PlanRiskAssessment(
            level=RiskLevel.LOW,
            reason="Empty plan with no actions",
            flagged_by="fast_path",
            confidence=1.0,
            matched_rule="empty_plan",
            step_assessments=[],
        )

    assessments: list[RiskAssessment] = []
    for step in steps:
        assessment = await check_action(step, classifier=classifier)
        assessments.append(assessment)

    overall_level = max_risk_level(s.level for s in assessments)

    if overall_level == RiskLevel.HIGH:
        high_step = next(s for s in assessments if s.level == RiskLevel.HIGH)
        reason = f"Plan contains high-risk step: {high_step.reason}"
        flagged_by = high_step.flagged_by
    elif overall_level == RiskLevel.MEDIUM:
        med_step = next(s for s in assessments if s.level == RiskLevel.MEDIUM)
        reason = f"Plan contains medium-risk step: {med_step.reason}"
        flagged_by = med_step.flagged_by
    else:
        reason = "All plan steps assessed as low risk"
        flagged_by = "fast_path"

    min_confidence = min((s.confidence for s in assessments), default=1.0)

    return PlanRiskAssessment(
        level=overall_level,
        reason=reason,
        flagged_by=flagged_by,
        confidence=min_confidence,
        matched_rule="plan_aggregated",
        step_assessments=assessments,
    )
