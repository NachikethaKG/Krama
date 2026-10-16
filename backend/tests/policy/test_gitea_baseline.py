"""Tests validating the safety policy against the agreed destructive Gitea action set."""

import json
from pathlib import Path

import pytest

from app.contracts_gen.common_schema import Action, Target
from app.policy.models import ActionContext, RiskLevel
from app.policy.risk import check_action
from app.policy.service import PolicyService
from app.ports.models import PageState, StepRef

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


# --- The same 30 cases through the Policy port, with a realistic PageState (no injected dialog_text) ---

_PLACEHOLDERS = {
    "{owner}": "demo",
    "{repo}": "policy-fixture",
    "{branch}": "feature-x",
    "{tag}": "v1.0.0",
    "{id}": "1",
    "{n}": "1",
}

# What the observer's ARIA excerpt (`main`) roughly shows on each crawled route. First match wins.
_ROUTE_ARIA: dict[str, list[str]] = {
    "/user/settings/account": [
        '- heading "Password" [level=4]',
        '- textbox "Current Password"',
        '- textbox "New Password"',
        '- textbox "Confirm Password"',
        '- button "Update Password"',
    ],
    "/user/settings": ['- heading "Profile" [level=4]', '- textbox "Full Name"', '- button "Update Profile"'],
    "/settings/hooks/": ['- heading "Update Webhook" [level=4]', '- textbox "Target URL *"'],
    "/settings": [
        '- heading "Settings" [level=4]',
        '- textbox "Repository Name *": policy-fixture',
        '- checkbox "Make repository private"',
        '- button "Update Settings"',
        '- link "How do I mirror repositories?"',
        '- button "Add Push Mirror"',
        '- heading "Danger Zone" [level=4]',
        '- button "Transfer Ownership"',
        '- button "Delete Wiki Data"',
        '- button "Archive Repo"',
        '- button "Delete This Repository"',
    ],
    "/branches": [
        '- heading "Branches" [level=4]',
        '- link "feature-x"',
        '- button "Rename Branch \\"feature-x\\""',
        '- button "Delete Branch \\"feature-x\\""',
    ],
    "/releases/edit/": [
        '- heading "Edit Release" [level=4]',
        '- textbox "Tag name"',
        '- button "Update Release"',
    ],
    "/labels": ['- heading "Labels" [level=4]', '- link "bug"', '- link "Edit"', '- link "Delete"'],
    "/milestones": ['- heading "Milestones" [level=4]', '- link "v1"', '- link "Close"', '- link "Delete"'],
    "/issues/": [
        '- heading "A policy fixture issue #1"',
        '- button "Close Issue"',
        '- button "Lock conversation"',
        '- textbox "Comment"',
        '- button "Drop files or click here to upload."',
    ],
}

# Gitea's open delete-branch dialog in the ARIA snapshot (phase-1-together-destructive-gitea-actions §2).
_GITEA_DIALOG = [
    "- text: Delete Branch feature-x",
    "- paragraph: Deleting a branch is permanent. Although the deleted branch may continue to exist for a"
    " short time before it actually gets removed, it CANNOT be undone in most cases. Continue?",
    '- button "No"',
    '- button "Yes"',
]


def _page_path(case: dict[str, str]) -> str:
    page = case["page"]
    if page.startswith("any page with an open"):
        return "/demo/policy-fixture/branches"
    if page == "any":
        return "/demo/policy-fixture"
    for placeholder, value in _PLACEHOLDERS.items():
        page = page.replace(placeholder, value)
    return page


def _target_name(case: dict[str, str]) -> str:
    name = case["name"]
    for placeholder, value in _PLACEHOLDERS.items():
        name = name.replace(placeholder, value)
    return name


def _realistic_page(case: dict[str, str], *, dialog_in_excerpt: bool) -> PageState:
    path = _page_path(case)
    name = _target_name(case)
    lines: list[str] = []
    for route, route_lines in _ROUTE_ARIA.items():
        if route in path:
            lines = list(route_lines)
            break
    if name == "Yes":
        # The dialog sits outside `main`, so the excerpt may or may not contain it.
        if dialog_in_excerpt:
            lines += _GITEA_DIALOG
    else:
        escaped = name.replace('"', '\\"')
        target_line = f'- {case["role"]} "{escaped}"'
        if target_line not in lines:
            lines.append(target_line)
    return PageState(url=path, title=f"{path} - Gitea", aria_excerpt="\n".join(lines))


def _realistic_cases() -> list[tuple[dict[str, str], bool]]:
    out: list[tuple[dict[str, str], bool]] = []
    for case in load_gitea_test_cases():
        out.append((case, True))
        if case["name"] == "Yes":
            out.append((case, False))
    return out


@pytest.mark.parametrize(
    ("case", "dialog_in_excerpt"),
    _realistic_cases(),
    ids=lambda v: (
        f"{v.get('page')}:{v.get('name')}:{v.get('risk')}" if isinstance(v, dict) else f"dialog={v}"
    ),
)
async def test_gitea_test_set_through_policy_service(case: dict[str, str], dialog_in_excerpt: bool) -> None:
    """Every high case pauses (destructive_action); every low and medium case is allowed."""
    name = _target_name(case)
    step = StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(name=name, role=case["role"]),
        instruction_text=f'Click "{name}"',
    )
    page = _realistic_page(case, dialog_in_excerpt=dialog_in_excerpt)

    decision = await PolicyService().check_action(step, page)

    if case["risk"] == "high":
        assert (decision.verdict, decision.reason) == ("pause", "destructive_action"), (case, decision)
    else:
        assert decision.verdict == "allow", (case, decision)


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
