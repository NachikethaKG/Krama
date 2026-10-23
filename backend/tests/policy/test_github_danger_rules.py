"""Automated unit and integration tests for GitHub danger-zone and security rules."""

import pytest

from app.policy.evaluator import PolicyEvaluator, evaluate_step
from app.policy.models import ActionContext, RiskLevel, StepRiskAssessment
from app.policy.risk import check_action
from app.policy.rules_github import (
    BRANCH_DELETE_SELECTOR_RE,
    GITHUB_DESTRUCTIVE_PHRASES,
    evaluate_github_danger_zone,
)


class TestGitHubDangerZoneHappyPath:
    """Verifies that high-consequence administrative and destructive actions evaluate to HIGH risk."""

    @pytest.mark.parametrize(
        ("url", "selector", "action_text", "expected_phrase"),
        [
            (
                "https://github.com/org/repo/settings",
                None,
                "Delete this repository",
                "delete this repository",
            ),
            (
                "https://github.com/org/repo/settings",
                "form[action*='/settings/delete'] button",
                "delete repository",
                "delete repository",
            ),
            (
                "https://github.com/org/repo/settings",
                None,
                "Change visibility",
                "change visibility",
            ),
            (
                "https://github.com/org/repo/settings",
                None,
                "Make public",
                "make public",
            ),
            (
                "https://github.com/org/repo/settings",
                None,
                "Make private",
                "make private",
            ),
            (
                "https://github.com/org/repo/settings",
                None,
                "Transfer ownership",
                "transfer ownership",
            ),
            (
                "https://github.com/org/repo/settings",
                None,
                "Archive this repository",
                "archive this repository",
            ),
        ],
    )
    def test_settings_danger_zone_actions(
        self,
        url: str,
        selector: str | None,
        action_text: str,
        expected_phrase: str,
    ) -> None:
        assessment = evaluate_github_danger_zone(
            url=url,
            target_selector=selector,
            action_text=action_text,
        )
        assert isinstance(assessment, StepRiskAssessment)
        assert assessment.risk_level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True
        assert "danger-zone" in assessment.reason.lower()
        assert expected_phrase in assessment.reason.lower()

    @pytest.mark.parametrize(
        ("action_text", "selector"),
        [
            ("Add deploy key", None),
            ("New key", None),
            ("Delete", "form[action*='/keys/'] button"),
            ("Revoke", None),
            (None, "button[aria-label='Revoke deploy key']"),
        ],
    )
    def test_deploy_keys_management(self, action_text: str | None, selector: str | None) -> None:
        assessment = evaluate_github_danger_zone(
            url="https://github.com/org/repo/settings/keys",
            target_selector=selector,
            action_text=action_text,
        )
        assert assessment.risk_level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True
        assert "deploy key" in assessment.reason.lower()

    @pytest.mark.parametrize(
        ("action_text", "selector"),
        [
            ("New repository secret", None),
            ("Delete secret", "button[aria-label='Delete secret']"),
            (None, None),  # Any action or navigation on /settings/secrets is flagged
            ("Update secret", None),
        ],
    )
    def test_secrets_management(self, action_text: str | None, selector: str | None) -> None:
        assessment = evaluate_github_danger_zone(
            url="https://github.com/org/repo/settings/secrets/actions",
            target_selector=selector,
            action_text=action_text,
        )
        assert assessment.risk_level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True
        assert "secrets" in assessment.reason.lower()

    @pytest.mark.parametrize(
        ("selector", "action_text"),
        [
            ("button[aria-label='Delete branch']", "trash"),
            ("button[title='Delete branch']", "delete"),
            ("form[action*='/branches/delete'] button", "confirm"),
            ("button[data-dialog-id='branch-delete-dialog']", None),
            ("button.js-branch-delete", "destroy branch"),
        ],
    )
    def test_branch_deletion_controls(self, selector: str, action_text: str | None) -> None:
        assessment = evaluate_github_danger_zone(
            url="https://github.com/org/repo/branches",
            target_selector=selector,
            action_text=action_text,
        )
        assert assessment.risk_level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True
        assert "branch deletion" in assessment.reason.lower()

    def test_cross_route_delete_branch_phrase(self) -> None:
        # e.g., on a merged PR page or modal dialog
        assessment = evaluate_github_danger_zone(
            url="https://github.com/org/repo/pull/42",
            target_selector="button",
            action_text="Delete branch",
        )
        assert assessment.risk_level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True


class TestGitHubDangerZoneSafePath:
    """Verifies that non-destructive GitHub workflows evaluate to LOW risk."""

    @pytest.mark.parametrize(
        ("url", "action_text", "selector"),
        [
            ("https://github.com/new", "Create repository", "button[type='submit']"),
            ("https://github.com/org/repo/issues/new", "Submit new issue", "button"),
            ("https://github.com/org/repo/labels", "New label", "button"),
            ("https://github.com/org/repo/branches", "New branch", "button"),
            ("https://github.com/org/repo/branches", "View all branches", "a"),
            ("https://github.com/org/repo", "Code", "a[aria-label='Code']"),
            ("https://github.com/org/repo", "Switch branches", "summary"),
            ("https://github.com/org/repo/edit/main/README.md", "Commit changes", "button"),
        ],
    )
    def test_benign_github_operations(
        self,
        url: str,
        action_text: str,
        selector: str,
    ) -> None:
        assessment = evaluate_github_danger_zone(
            url=url,
            target_selector=selector,
            action_text=action_text,
        )
        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.requires_confirmation is False
        assert "safe" in assessment.reason.lower()


class TestGitHubDangerZoneEdgeCases:
    """Verifies robustness against empty inputs, missing selectors, and casing anomalies."""

    def test_empty_and_none_parameters(self) -> None:
        assessment = evaluate_github_danger_zone(
            url="",
            target_selector=None,
            action_text=None,
        )
        assert assessment.risk_level == RiskLevel.LOW
        assert assessment.requires_confirmation is False

    @pytest.mark.parametrize(
        ("url", "action_text"),
        [
            ("https://github.com/org/repo/settings", "DELETE THIS REPOSITORY"),
            ("https://github.com/org/repo/settings", "ChAnGe ViSiBiLiTy"),
            ("https://github.com/org/repo/settings/keys", "ADD DEPLOY KEY"),
            ("https://github.com/org/repo/branches", "DELETE BRANCH"),
            ("https://github.com/org/repo/branches", "TRASH"),
        ],
    )
    def test_case_insensitive_matching(self, url: str, action_text: str) -> None:
        assessment = evaluate_github_danger_zone(
            url=url,
            target_selector=None,
            action_text=action_text,
        )
        assert assessment.risk_level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True

    def test_branch_delete_selector_regex(self) -> None:
        assert BRANCH_DELETE_SELECTOR_RE.search("branch-delete-dialog")
        assert BRANCH_DELETE_SELECTOR_RE.search("button-delete-this-branch")
        assert BRANCH_DELETE_SELECTOR_RE.search("form[action='/branches/delete']")
        assert not BRANCH_DELETE_SELECTOR_RE.search("button-create-new-branch")

    def test_destructive_phrases_coverage(self) -> None:
        assert "delete this repository" in GITHUB_DESTRUCTIVE_PHRASES
        assert "change visibility" in GITHUB_DESTRUCTIVE_PHRASES
        assert "delete branch" in GITHUB_DESTRUCTIVE_PHRASES
        assert "make public" in GITHUB_DESTRUCTIVE_PHRASES
        assert "make private" in GITHUB_DESTRUCTIVE_PHRASES


class TestEvaluatorIntegration:
    """Verifies evaluate_step and PolicyEvaluator helper integration."""

    def test_evaluate_step_github_danger_zone(self) -> None:
        result = evaluate_step(
            action="Delete this repository",
            url="https://github.com/org/repo/settings",
        )
        assert isinstance(result, StepRiskAssessment)
        assert result.risk_level == RiskLevel.HIGH
        assert result.requires_confirmation is True

    def test_policy_evaluator_evaluate_helper(self) -> None:
        result = PolicyEvaluator.evaluate(
            action="New repository secret",
            url="https://github.com/org/repo/settings/secrets/actions",
        )
        assert result.risk_level == RiskLevel.HIGH
        assert result.requires_confirmation is True

    def test_evaluate_step_safe_path(self) -> None:
        result = evaluate_step(
            action="New branch",
            url="https://github.com/org/repo/branches",
        )
        assert result.risk_level == RiskLevel.LOW
        assert result.requires_confirmation is False

    @pytest.mark.anyio
    async def test_risk_check_action_integration(self) -> None:
        ctx = ActionContext(
            url="https://github.com/org/repo/settings",
            title="Repository Settings · GitHub",
        )
        assessment = await check_action(
            action="Delete this repository",
            context=ctx,
        )
        assert assessment.level == RiskLevel.HIGH
        assert assessment.flagged_by in ("github_danger_zone", "denylist")

    @pytest.mark.anyio
    async def test_risk_check_action_safe_branch_create(self) -> None:
        ctx = ActionContext(
            url="https://github.com/org/repo/branches",
            title="Branches · GitHub",
        )
        assessment = await check_action(
            action="New branch",
            context=ctx,
        )
        assert assessment.level == RiskLevel.LOW
