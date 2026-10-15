"""Unit tests for policy risk models and enums."""

import pytest
from pydantic import ValidationError

from app.policy.models import (
    ActionContext,
    PlanRiskAssessment,
    RiskAssessment,
    RiskLevel,
    max_risk_level,
)


def test_risk_level_values_and_comparisons() -> None:
    assert RiskLevel.LOW.value == "low"
    assert RiskLevel.MEDIUM.value == "medium"
    assert RiskLevel.HIGH.value == "high"
    assert RiskLevel("low") is RiskLevel.LOW

    assert max_risk_level([RiskLevel.LOW, RiskLevel.MEDIUM]) == RiskLevel.MEDIUM
    assert max_risk_level([RiskLevel.LOW, RiskLevel.HIGH, RiskLevel.MEDIUM]) == RiskLevel.HIGH
    assert max_risk_level([]) == RiskLevel.LOW


def test_risk_assessment_validation() -> None:
    assessment = RiskAssessment(
        level=RiskLevel.HIGH,
        reason="Dangerous action",
        flagged_by="denylist",
        matched_rule="test_rule",
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.confidence == 1.0
    assert assessment.matched_rule == "test_rule"

    # Frozen model cannot be modified
    with pytest.raises(ValidationError):
        assessment.level = RiskLevel.LOW  # type: ignore[misc]

    # Extra fields are forbidden
    with pytest.raises(ValidationError):
        RiskAssessment(
            level=RiskLevel.LOW,
            reason="Ok",
            flagged_by="fast_path",
            extra_field="invalid",  # type: ignore[call-arg]
        )


def test_plan_risk_assessment_subclass() -> None:
    step1 = RiskAssessment(level=RiskLevel.LOW, reason="Step 1 ok", flagged_by="fast_path")
    step2 = RiskAssessment(level=RiskLevel.HIGH, reason="Step 2 delete", flagged_by="denylist")

    plan_assessment = PlanRiskAssessment(
        level=RiskLevel.HIGH,
        reason="Plan contains dangerous step",
        flagged_by="denylist",
        step_assessments=[step1, step2],
    )

    assert isinstance(plan_assessment, RiskAssessment)
    assert plan_assessment.level == RiskLevel.HIGH
    assert len(plan_assessment.step_assessments) == 2


def test_action_context_defaults() -> None:
    ctx = ActionContext(url="/repo/settings", title="Settings")
    assert ctx.url == "/repo/settings"
    assert ctx.title == "Settings"
    assert ctx.aria_excerpt == ""
    assert ctx.dialog_text is None
    assert ctx.previous_step is None
