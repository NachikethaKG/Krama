"""Tests for plan risk assessment aggregating multi-step plans."""

import pytest

from app.contracts_gen.common_schema import Action, Target
from app.llm import FakeProvider, FakeResponse
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
    llm = FakeProvider(
        [
            FakeResponse(
                name="draft_low",
                schema_name="RiskVerdict",
                response={"level": "low", "reason": "Draft discard is benign"},
            )
        ]
    )
    classifier = LLMClassifier(llm)
    plan = [{"name": "Delete draft comment", "role": "button"}]

    assessment = await assess_plan(plan, classifier=classifier)
    assert assessment.level == RiskLevel.LOW
    assert assessment.step_assessments[0].flagged_by == "llm_classifier"


def _ref(seq: int, name: str, instruction: str) -> StepRef:
    return StepRef(
        seq=seq,
        action=Action(type="click"),
        target=Target(name=name, role="button"),
        instruction_text=instruction,
    )


async def test_assess_plan_generic_confirm_inherits_previous_step() -> None:
    """Each step is assessed with the previous step as context (review finding: context was ignored)."""
    draft = PlanDraft(
        task="Delete the feature-x branch",
        steps=[
            _ref(1, 'Delete Branch "feature-x"', "Open the delete dialog"),
            _ref(2, "Yes", "Confirm"),
        ],
    )
    assessment = await assess_plan(draft)
    assert assessment.step_assessments[1].level == RiskLevel.HIGH
    assert assessment.step_assessments[1].matched_rule == "gitea_dialog_confirm_destructive"


async def test_assess_plan_generic_confirm_after_benign_step_is_low() -> None:
    draft = PlanDraft(
        task="Apply the default labels",
        steps=[
            _ref(1, "Use default label set", "Open the default label dialog"),
            _ref(2, "Yes", "Confirm"),
        ],
    )
    assessment = await assess_plan(draft)
    assert assessment.step_assessments[1].level == RiskLevel.LOW


async def test_assess_plan_first_step_generic_confirm_is_high() -> None:
    draft = PlanDraft(task="Confirm", steps=[_ref(1, "OK", "Confirm")])
    assessment = await assess_plan(draft)
    assert assessment.level == RiskLevel.HIGH
