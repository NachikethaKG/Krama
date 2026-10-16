"""Core risk assessment engine for browser actions and plans.

What is matched:
- the target control (role + accessible name) and the page route, against the Gitea baseline and the
  denylist verbs;
- the instruction's own words, with the typed value removed (and, for typing actions, every quoted
  phrase removed), so "Delete branch drafts" on a bare `Delete` counts but an issue titled "Delete old docs"
  does not.

What is never used: the value an action types. It is not matched, and it never appears in a reason, a
message or a log line (the reason ends up in the run's pause event).
"""

import re
from collections.abc import Sequence
from typing import Any

from app.policy.classifier import LLMClassifier
from app.policy.denylist import (
    GENERIC_CONFIRM_NAMES,
    check_gitea_baseline,
    hard_destructive_keywords,
    is_ambiguous,
    is_benign,
    is_destructive_dialog_text,
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

# Actions whose value is typed data, not a choice of control.
_TYPING_ACTIONS = frozenset({"fill", "select", "press", "type"})
_QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'|‘[^’]*’")  # noqa: RUF001 (typographic quotes on purpose)
# One line of a Playwright ARIA snapshot: `- role "name" [attrs]: text` or `- text: some text`.
_ARIA_LINE = re.compile(
    r'^\s*-\s*(?P<role>[a-z]+)(?:\s+"(?P<name>(?:[^"\\]|\\.)*)")?[^:]*(?::\s*(?P<text>.*))?$'
)
_CONTEXT_ROLES = frozenset(
    {"text", "paragraph", "heading", "strong", "emphasis", "generic", "dialog", "alert"}
)
_SIBLING_BUTTON_NAMES = frozenset({"no", "cancel", "close", "dismiss"})
_MAX_CONTEXT_LINES = 3


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


def _strip_value(text: str, value: str, action_type: str) -> str:
    """`text` without the typed value, and for typing actions without any quoted phrase."""
    if value.strip():
        text = re.sub(re.escape(value.strip()), " ", text, flags=re.IGNORECASE)
    if action_type.lower() in _TYPING_ACTIONS:
        text = _QUOTED.sub(" ", text)
    return " ".join(text.split())


def _describe_target(name: str, role: str) -> str:
    if role and name:
        return f'{role} "{name}"'
    return f'"{name}"' if name else (role or "the target")


def _step_summary(name: str, role: str, action_type: str, intent: str) -> str:
    """What the LLM classifier sees about the step: role, name, action type and instruction, no value."""
    lines = [f"action: {action_type}", f"target: {_describe_target(name, role)}"]
    if intent:
        lines.append(f"instruction: {intent}")
    return "\n".join(lines)


def _text_before_control(aria_excerpt: str, name: str) -> str | None:
    """The text just before the last control named `name` in an ARIA snapshot.

    Gitea dialogs have no dialog role: the dialog is text + paragraph + "No" + "Yes". None if the control,
    or any text right before it, isn't there."""
    lines = aria_excerpt.splitlines()
    wanted = name.strip().lower()
    index = None
    for i, line in enumerate(lines):
        m = _ARIA_LINE.match(line)
        if m and (m.group("name") or "").strip().lower() == wanted and m.group("role") != "text":
            index = i
    if index is None:
        return None

    collected: list[str] = []
    for line in reversed(lines[:index]):
        m = _ARIA_LINE.match(line)
        if not m:
            continue
        role = m.group("role")
        label = (m.group("name") or "").strip()
        if role == "button" and label.lower() in _SIBLING_BUTTON_NAMES and not collected:
            continue  # the "No" / "Cancel" next to the "Yes"
        if role in _CONTEXT_ROLES:
            text = " ".join(p for p in (label, (m.group("text") or "").strip()) if p)
            if text:
                collected.append(text)
            if len(collected) >= _MAX_CONTEXT_LINES:
                break
            continue
        if collected:
            break  # another control: the dialog text ends here
        # A control right before the confirm (no dialog text in between): no context.
        break
    if not collected:
        return None
    return " ".join(reversed(collected))


def _check_generic_confirm(name: str, intent: str, ctx: ActionContext) -> RiskAssessment:
    """A generic confirm ("Yes", "OK", ...) inherits the risk of the dialog text before it; HIGH without."""
    if hard_destructive_keywords(intent):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason=f"Confirmation '{name}' of a destructive step",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="generic_confirm_destructive_instruction",
        )
    dialog = ctx.dialog_text or _text_before_control(ctx.aria_excerpt, name) or ctx.previous_step
    if not dialog:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason=f"Generic confirmation '{name}' without visible dialog context; a human must confirm",
            flagged_by="fallback_safe",
            confidence=1.0,
            matched_rule="generic_confirm_without_context",
        )
    if is_destructive_dialog_text(dialog):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason=f"Confirmation '{name}' inherits destructive dialog risk",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_dialog_confirm_destructive",
        )
    return RiskAssessment(
        level=RiskLevel.LOW,
        reason=f"Confirmation '{name}' of a non-destructive dialog",
        flagged_by="fast_path",
        confidence=0.9,
        matched_rule="generic_confirm_benign_context",
    )


async def check_action(
    action: Any,
    context: Any = None,
    *,
    classifier: LLMClassifier | None = None,
) -> RiskAssessment:
    """Classify a single action into low, medium, or high risk.

    1. Generic confirmations inherit the dialog's risk (HIGH when no dialog text is found).
    2. Benign fast-path for known false positives (Cancel, docs links, ...).
    3. Gitea baseline rules on (role, name, route).
    4. Ambiguous scope ("delete draft") goes to the LLM classifier; without a verdict it stays HIGH.
    5. Denylist verbs on the target or the instruction: HIGH.
    """
    name, role, action_type, action_value, instruction = _normalize_action(action)
    ctx = _normalize_context(context)
    intent = _strip_value(instruction, action_value, action_type)
    target = name or intent
    target_desc = _describe_target(target, role)

    # 1. Generic confirmation buttons
    if target.strip().lower() in GENERIC_CONFIRM_NAMES:
        return _check_generic_confirm(target.strip(), intent, ctx)

    # 2. Benign fast-path
    benign_match = is_benign(target, role, ctx.url)
    if benign_match:
        return benign_match

    # 3. Gitea baseline rules (HIGH wins at once; a MEDIUM still loses to a destructive verb below)
    baseline_match = check_gitea_baseline(target, role, ctx.url)
    if baseline_match and baseline_match.level == RiskLevel.HIGH:
        return baseline_match

    match_text = " ".join(p for p in (target, intent) if p)

    # 4. Ambiguous scope ("delete draft", "reset filter"): the LLM decides; no verdict means a safe fallback.
    if is_ambiguous(match_text):
        clf = classifier or LLMClassifier()
        return await clf.classify(_step_summary(target, role, action_type, intent), ctx)

    # 5. Deterministic denylist on the target control, then on the instruction's own words
    for text, where in ((target, "target"), (intent, "instruction")):
        matched = match_denylist_keywords(text)
        if matched:
            kw = matched[0]
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reason=f"Action matches denylist keyword '{kw}' in the {where} ({target_desc})",
                flagged_by="denylist",
                confidence=1.0,
                matched_rule=f"denylist_keyword_{kw}",
            )

    if baseline_match:
        return baseline_match

    # 6. Default benign action
    return RiskAssessment(
        level=RiskLevel.LOW,
        reason=f"Benign interaction: {target_desc}",
        flagged_by="fast_path",
        confidence=1.0,
        matched_rule="default_low",
    )


def _previous_step_text(step: Any) -> str:
    """What a step did, as context for the next one (a generic "Yes" after `Delete Branch "x"`). No value."""
    name, role, action_type, action_value, instruction = _normalize_action(step)
    intent = _strip_value(instruction, action_value, action_type)
    return " ".join(p for p in (_describe_target(name, role) if name else "", intent) if p)


async def assess_plan(
    plan: Any,
    *,
    classifier: LLMClassifier | None = None,
) -> PlanRiskAssessment:
    """Classify an entire plan by assessing all steps and aggregating the risk.

    Each step is checked with the previous step as its context, so a generic confirm right after a destructive
    opener inherits its risk.
    """
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
    previous: str | None = None
    for step in steps:
        assessment = await check_action(step, ActionContext(previous_step=previous), classifier=classifier)
        assessments.append(assessment)
        previous = _previous_step_text(step) or None

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
