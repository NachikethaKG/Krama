"""Tests for plan risk assessment aggregating multi-step plans."""

import pytest

from app.contracts_gen.common_schema import Action, Target
from app.policy.classifier import LLMClassifier
from app.policy.models import PlanRiskAssessment, RiskLevel
from app.policy.risk import assess_plan
from app.ports.models import PlanDraft, StepRef

pytestmark = pytest.mark.anyio


async def test_assess_plan_all_low_risk_steps() -> None:
    plan = {
        "steps": [
            {"name": "Click Issues", "role": "link"},
            {"name": "New Issue", "role": "button"},
            {"name": "Submit", "role": "button"},
        ]
    }
    assessment = await assess_plan(plan)
    assert isinstance(assessment, PlanRiskAssessment)
    assert assessment.level == RiskLevel.LOW
    assert len(assessment.step_assessments) == 3
    assert all(s.level == RiskLevel.LOW for s in assessment.step_assessments)


async def test_assess_plan_with_medium_risk_step() -> None:
    plan = {
        "steps": [
            {"name": "Open Issue #42", "role": "link"},
            {"name": "Close Issue", "role": "button"},
        ]
    }
    assessment = await assess_plan(plan)
    assert assessment.level == RiskLevel.MEDIUM
    assert assessment.step_assessments[1].level == RiskLevel.MEDIUM
    assert "medium-risk step" in assessment.reason


async def test_assess_plan_with_high_risk_step() -> None:
    plan = {
        "steps": [
            {"name": "Open Settings", "role": "link"},
            {"name": "Delete This Repository", "role": "button"},
        ]
    }
    assessment = await assess_plan(plan)
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"
    assert assessment.step_assessments[1].level == RiskLevel.HIGH


async def test_assess_plan_with_plan_draft_model() -> None:
    step1 = StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(name="Branches", role="link"),
        instruction_text="Open branches",
    )
    step2 = StepRef(
        seq=2,
        action=Action(type="click"),
        target=Target(name='Delete Branch "feature-x"', role="button"),
        instruction_text="Delete the branch",
    )
    draft = PlanDraft(task="Clean up old branches", steps=[step1, step2])

    assessment = await assess_plan(draft)
    assert assessment.level == RiskLevel.HIGH
    assert len(assessment.step_assessments) == 2
    assert assessment.step_assessments[0].level == RiskLevel.LOW
    assert assessment.step_assessments[1].level == RiskLevel.HIGH


async def test_assess_plan_string_task() -> None:
    benign_plan = await assess_plan("Create a new issue with label bug")
    assert benign_plan.level == RiskLevel.LOW

    risky_plan = await assess_plan("Delete the production repository")
    assert risky_plan.level == RiskLevel.HIGH


async def test_assess_plan_empty() -> None:
    empty_plan = await assess_plan([])
    assert empty_plan.level == RiskLevel.LOW
    assert "Empty plan" in empty_plan.reason


async def test_assess_plan_disambiguation_with_llm() -> None:
    class FakeDraftLLM:
        async def __call__(self, prompt: str, system: str | None = None) -> str:
            return '{"level": "low", "reason": "Draft discard is benign"}'

    classifier = LLMClassifier(llm=FakeDraftLLM())
    plan = [{"name": "Delete draft comment", "role": "button"}]

    assessment = await assess_plan(plan, classifier=classifier)
    assert assessment.level == RiskLevel.LOW
    assert assessment.step_assessments[0].flagged_by == "llm_classifier"
