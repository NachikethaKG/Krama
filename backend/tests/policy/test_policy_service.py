"""Tests for PolicyService adapting to the backend Policy port."""

from datetime import UTC, datetime

import pytest

from app.contracts_gen.common_schema import Action, Target
from app.llm import FakeProvider, FakeResponse
from app.policy.classifier import LLMClassifier
from app.policy.service import PolicyService
from app.ports.models import (
    ObservedState,
    PageState,
    PlanDraft,
    RiskReport,
    StepRef,
)
from app.ports.policy import Policy

pytestmark = pytest.mark.anyio


def test_policy_service_conforms_to_policy_protocol() -> None:
    service = PolicyService()
    # Typed protocol conformance (mypy enforces compile time; runtime verifies method signatures)
    policy: Policy = service
    assert callable(policy.assess_plan)
    assert callable(policy.check_action)
    assert callable(policy.mask)


async def test_policy_service_assess_plan() -> None:
    service = PolicyService()
    step1 = StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(name="Settings", role="link"),
        instruction_text="Navigate to settings",
    )
    step2 = StepRef(
        seq=2,
        action=Action(type="click"),
        target=Target(name="Delete Repository", role="button"),
        instruction_text="Click delete repository",
    )
    draft = PlanDraft(task="Delete the repository", steps=[step1, step2])

    report: RiskReport = await service.assess_plan(draft)
    assert report.level == "high"
    assert len(report.steps) == 2
    assert report.steps[0].seq == 1
    assert report.steps[0].risk == "low"
    assert report.steps[1].seq == 2
    assert report.steps[1].risk == "high"
    assert "repository deletion" in report.steps[1].reason.lower()


async def test_policy_service_check_action_high_risk_pauses() -> None:
    service = PolicyService()
    step = StepRef(
        seq=3,
        action=Action(type="click"),
        target=Target(name="Transfer Ownership", role="button"),
        instruction_text="Transfer repository",
    )
    page = PageState(url="/owner/repo/settings", title="Settings")

    decision = await service.check_action(step, page)
    assert decision.verdict == "pause"
    assert decision.reason == "destructive_action"
    assert "transferring repository ownership" in decision.message.lower()


async def test_policy_service_check_action_low_risk_allows() -> None:
    service = PolicyService()
    step = StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(name="New Issue", role="link"),
        instruction_text="Open new issue form",
    )
    page = PageState(url="/owner/repo/issues", title="Issues")

    decision = await service.check_action(step, page)
    assert decision.verdict == "allow"
    assert decision.reason == "ok"


async def test_policy_service_check_action_disambiguation() -> None:
    llm = FakeProvider(
        [
            FakeResponse(
                name="draft_low",
                schema_name="RiskVerdict",
                response={"level": "low", "reason": "Draft is temporary"},
            )
        ]
    )
    classifier = LLMClassifier(llm)
    service = PolicyService(classifier=classifier)

    step = StepRef(
        seq=2,
        action=Action(type="click"),
        target=Target(name="Delete draft", role="button"),
        instruction_text="Discard current draft comment",
    )
    page = PageState(url="/owner/repo/issues/1", title="Issue #1")

    decision = await service.check_action(step, page)
    assert decision.verdict == "allow"
    assert decision.reason == "ok"
    assert "Draft is temporary" in decision.message


def test_policy_service_mask_observed_state() -> None:
    service = PolicyService()
    observed = ObservedState(
        url="/login",
        title="Login",
        captured_at=datetime.now(UTC),
    )
    masked = service.mask(observed)
    assert masked.url == observed.url
    assert masked.title == observed.title

    # Test masking of sensitive credentials
    sensitive_observed = ObservedState(
        url="/auth?token=secret_token_123456",
        title="Admin password=SuperSecretP@ssword123!",
        headings=["Welcome", "API key: sk-12345678901234567890"],
        aria_excerpt='- textbox "Password": MySecretPass999',
        captured_at=datetime.now(UTC),
    )
    masked_sensitive = service.mask(sensitive_observed)
    assert "secret_token_123456" not in masked_sensitive.url
    assert "[REDACTED]" in masked_sensitive.url
    assert "SuperSecretP@ssword123!" not in masked_sensitive.title
    assert "[REDACTED]" in masked_sensitive.title
    assert "sk-12345678901234567890" not in masked_sensitive.headings[1]
    assert "[REDACTED]" in masked_sensitive.headings[1]
    assert "MySecretPass999" not in masked_sensitive.aria_excerpt
    assert "[REDACTED]" in masked_sensitive.aria_excerpt
