"""Tests for fast-path keyword denylist and benign filters."""

import pytest

from app.policy.denylist import DENYLIST_KEYWORDS
from app.policy.models import RiskLevel
from app.policy.risk import check_action

pytestmark = pytest.mark.anyio


def test_denylist_contains_all_agreed_keywords() -> None:
    expected = {"delete", "purchase", "transfer", "publish", "send", "reset", "security"}
    assert expected.issubset(DENYLIST_KEYWORDS)


@pytest.mark.parametrize(
    ("action_text", "matched_keyword"),
    [
        ("delete repository", "delete"),
        ("deletes database", "delete"),
        ("purchase credits", "purchase"),
        ("buy subscription license", "purchase"),
        ("transfer ownership of repo", "transfer"),
        ("publish release v1.0.0", "publish"),
        ("send payment transaction", "send"),
        ("reset password", "reset"),
        ("factory reset device", "reset"),
        ("security credential revoke", "security"),
        ("update password and token", "security"),
        ("revoke SSH key", "security"),
        ("revoke GPG key", "security"),
    ],
)
async def test_denylist_keywords_trigger_high_risk(action_text: str, matched_keyword: str) -> None:
    assessment = await check_action(action_text)
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"
    assert matched_keyword in assessment.reason.lower() or matched_keyword in (assessment.matched_rule or "")


@pytest.mark.parametrize(
    "action_text",
    [
        "click link",
        "view issue",
        "create label",
        "create repository",
        "read documentation",
        "open issues tab",
        "type search query",
        "inspect commits",
    ],
)
async def test_happy_path_benign_actions_return_low_risk(action_text: str) -> None:
    assessment = await check_action(action_text)
    assert assessment.level == RiskLevel.LOW
    assert assessment.flagged_by == "fast_path"


@pytest.mark.parametrize(
    ("name", "role", "url"),
    [
        ("Cancel", "button", "/any/page"),
        ("No", "button", "/any/page"),
        ("Unwatch", "button", "/owner/repo"),
        ("How do I mirror repositories?", "link", "/owner/repo/settings"),
        ("Drop files or click here to upload.", "button", "/owner/repo/issues/1"),
        ("Private", "link", "/"),
    ],
)
async def test_benign_controls_avoid_false_positives(name: str, role: str, url: str) -> None:
    assessment = await check_action({"name": name, "role": role}, {"url": url})
    assert assessment.level == RiskLevel.LOW
    assert assessment.flagged_by == "fast_path"
