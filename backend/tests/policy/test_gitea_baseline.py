"""Tests validating the safety policy against the agreed destructive Gitea action set."""

import json
from pathlib import Path

import pytest

from app.policy.models import ActionContext, RiskLevel
from app.policy.risk import check_action

pytestmark = pytest.mark.anyio

ROOT_DIR = Path(__file__).resolve().parents[3]
GITEA_TEST_SET_PATH = (
    ROOT_DIR
    / "docs"
    / "research"
    / "assets"
    / "phase-1-together-policy-and-verification"
    / "gitea-policy-test-set.json"
)


def load_gitea_test_cases() -> list[dict[str, str]]:
    if not GITEA_TEST_SET_PATH.exists():
        pytest.skip(f"Test set fixture not found at {GITEA_TEST_SET_PATH}")
    with open(GITEA_TEST_SET_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return list(data.get("cases", []))


@pytest.mark.parametrize(
    "case",
    load_gitea_test_cases(),
    ids=lambda c: f"{c.get('page')}:{c.get('name')}:{c.get('risk')}",
)
async def test_gitea_policy_test_set_cases(case: dict[str, str]) -> None:
    expected_risk = case["risk"]
    page_url = case["page"]
    role = case["role"]
    name = case["name"]

    context = ActionContext(
        url=page_url,
        title="Gitea",
        dialog_text="Delete Branch feature-x ... CANNOT be undone in most cases. Continue?"
        if name == "Yes"
        else None,
        previous_step="Click Delete Branch" if name == "Yes" else None,
    )

    assessment = await check_action({"name": name, "role": role}, context)
    assert assessment.level.value == expected_risk, (
        f"Mismatch for case '{name}' on '{page_url}': expected {expected_risk}, got {assessment.level.value} "
        f"(reason: {assessment.reason}, rule: {assessment.matched_rule})"
    )


async def test_destructive_gitea_delete_repository() -> None:
    assessment = await check_action(
        {"name": "Delete This Repository", "role": "button"},
        ActionContext(url="/owner/my-repo/settings"),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"


async def test_destructive_gitea_transfer_ownership() -> None:
    assessment = await check_action(
        {"name": "Transfer Ownership", "role": "button"},
        ActionContext(url="/owner/my-repo/settings"),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"


async def test_destructive_gitea_revoke_ssh_key() -> None:
    assessment = await check_action(
        {"name": "Revoke SSH Key", "role": "button"},
        ActionContext(url="/user/settings/keys"),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"


async def test_destructive_gitea_revoke_gpg_key() -> None:
    assessment = await check_action(
        {"name": "Revoke GPG Key", "role": "button"},
        ActionContext(url="/user/settings/keys"),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"


async def test_destructive_gitea_delete_branch() -> None:
    assessment = await check_action(
        {"name": 'Delete Branch "feature-x"', "role": "button"},
        ActionContext(url="/owner/my-repo/branches"),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"


async def test_destructive_gitea_purge_wiki() -> None:
    assessment = await check_action(
        {"name": "Delete Wiki Data", "role": "button"},
        ActionContext(url="/owner/my-repo/settings"),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"


async def test_destructive_gitea_generic_yes_confirmation_in_dialog() -> None:
    assessment = await check_action(
        {"name": "Yes", "role": "button"},
        ActionContext(
            url="/owner/my-repo/branches",
            dialog_text=(
                "Delete Branch feature-x. Deleting a branch is permanent. CANNOT be undone. Continue?"
            ),
        ),
    )
    assert assessment.level == RiskLevel.HIGH
    assert assessment.flagged_by == "denylist"
