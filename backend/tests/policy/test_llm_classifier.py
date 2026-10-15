"""Tests for LLM classifier fallback, contextual disambiguation, and fail-safe error handling."""

import asyncio

import pytest

from app.policy.classifier import LLMClassifier
from app.policy.models import ActionContext, RiskLevel
from app.policy.risk import check_action

pytestmark = pytest.mark.anyio


class MockLLM:
    """Mock LLM returning predefined JSON classification."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.call_count = 0
        self.last_prompt = ""

    async def __call__(self, prompt: str, system: str | None = None) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return self.response


class TimeoutLLM:
    """Mock LLM that simulates network timeout."""

    async def __call__(self, prompt: str, system: str | None = None) -> str:
        await asyncio.sleep(5.0)
        return '{"level": "low"}'


class ErrorLLM:
    """Mock LLM that simulates an API error."""

    async def __call__(self, prompt: str, system: str | None = None) -> str:
        raise RuntimeError("503 Service Unavailable: Gemini overloaded")


async def test_llm_classifier_disambiguates_delete_draft_vs_delete_repository() -> None:
    # 1. Unambiguous "delete repository" is caught immediately by the deterministic denylist
    mock_llm = MockLLM('{"level": "low", "reason": "Should not be called"}')
    classifier = LLMClassifier(llm=mock_llm)

    repo_assessment = await check_action("delete repository", classifier=classifier)
    assert repo_assessment.level == RiskLevel.HIGH
    assert repo_assessment.flagged_by == "denylist"
    assert mock_llm.call_count == 0  # Fast-path handled it; LLM not invoked

    # 2. Ambiguous "delete draft" invokes the LLM classifier to disambiguate
    draft_llm = MockLLM('{"level": "low", "reason": "Draft is temporary and not persistent in the repo"}')
    draft_classifier = LLMClassifier(llm=draft_llm)

    draft_assessment = await check_action("delete draft comment", classifier=draft_classifier)
    assert draft_assessment.level == RiskLevel.LOW
    assert draft_assessment.flagged_by == "llm_classifier"
    assert "Draft is temporary" in draft_assessment.reason
    assert draft_llm.call_count == 1


async def test_llm_classifier_timeout_fails_safely_to_high_risk() -> None:
    timeout_classifier = LLMClassifier(llm=TimeoutLLM(), timeout_s=0.05, fallback_level=RiskLevel.HIGH)

    assessment = await check_action("delete draft", classifier=timeout_classifier)
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "fallback_safe"
    assert "timed out" in assessment.reason


async def test_llm_classifier_api_error_fails_safely_to_high_risk() -> None:
    error_classifier = LLMClassifier(llm=ErrorLLM(), fallback_level=RiskLevel.HIGH)

    assessment = await check_action("delete draft", classifier=error_classifier)
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "fallback_safe"
    assert "API error" in assessment.reason
    assert "503 Service Unavailable" in assessment.reason


async def test_llm_classifier_malformed_json_fails_safely() -> None:
    bad_json_llm = MockLLM("This is not JSON at all")
    classifier = LLMClassifier(llm=bad_json_llm)

    assessment = await check_action("delete draft", classifier=classifier)
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "fallback_safe"


async def test_llm_classifier_custom_fallback_level() -> None:
    error_classifier = LLMClassifier(llm=ErrorLLM(), fallback_level=RiskLevel.MEDIUM)

    assessment = await check_action("delete draft", classifier=error_classifier)
    assert assessment.level == RiskLevel.MEDIUM
    assert assessment.flagged_by == "fallback_safe"


async def test_heuristic_fallback_when_no_llm_provided() -> None:
    classifier = LLMClassifier(llm=None)

    draft = await classifier.classify("Discard draft response", ActionContext())
    assert draft.level == RiskLevel.LOW
    assert "draft" in draft.reason.lower()

    view = await classifier.classify("reset zoom filter", ActionContext())
    assert view.level == RiskLevel.LOW
    assert "view or filter" in view.reason.lower()

    unknown = await classifier.classify("ambiguous_unrecognized_action", ActionContext())
    assert unknown.level == RiskLevel.HIGH
    assert unknown.flagged_by == "fallback_safe"
