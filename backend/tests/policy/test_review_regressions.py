"""Regression tests for the policy review findings (#61, #62): wrongly allowed destructive actions,
over-pausing on typed values, and secrets leaking into decision messages or logs."""

import logging
from typing import Literal

import pytest
from pydantic import BaseModel

from app.contracts_gen.common_schema import Action, Target
from app.llm import LLMError, LLMResult
from app.policy.classifier import LLMClassifier
from app.policy.models import ActionContext, RiskLevel
from app.policy.risk import check_action
from app.policy.service import PolicyService
from app.ports.models import PageState, PlanDraft, StepRef

ActionKind = Literal["click", "fill", "select", "navigate", "press", "wait"]

pytestmark = pytest.mark.anyio

# How Gitea renders an open delete dialog in the ARIA snapshot (no dialog role: text, paragraph, No, Yes).
# docs/research/phase-1-together-destructive-gitea-actions.md §2
GITEA_DELETE_BRANCH_DIALOG = "\n".join(
    [
        "- text: Delete Branch feature-x",
        "- paragraph: Deleting a branch is permanent. Although the deleted branch may continue to exist for a"
        " short time before it actually gets removed, it CANNOT be undone in most cases. Continue?",
        '- button "No"',
        '- button "Yes"',
    ]
)


def _step(
    name: str, role: str, instruction: str, *, action: ActionKind = "click", value: str | None = None
) -> StepRef:
    return StepRef(
        seq=1,
        action=Action(type=action, value=value),
        target=Target(name=name, role=role),
        instruction_text=instruction,
    )


# --- 3a: bare "Delete" + an ambiguous-looking instruction was downgraded to LOW without an LLM ---


async def test_bare_delete_with_drafts_instruction_pauses_without_llm() -> None:
    step = _step("Delete", "button", "Delete branch drafts")
    page = PageState(url="/demo/repo/branches", title="Branches", aria_excerpt='- button "Delete"')

    decision = await PolicyService().check_action(step, page)

    assert decision.verdict == "pause"
    assert decision.reason == "destructive_action"


async def test_bare_delete_on_unknown_route_is_high() -> None:
    assessment = await check_action(
        {"name": "Delete", "role": "button"}, ActionContext(url="/demo/repo/branches")
    )
    assert assessment.level == RiskLevel.HIGH


# --- 3b: the docs fast-path allowed "Delete docs" / "Delete guide page" ---


@pytest.mark.parametrize(("name", "role"), [("Delete docs", "button"), ("Delete guide page", "link")])
async def test_docs_fast_path_skipped_for_destructive_verb(name: str, role: str) -> None:
    assessment = await check_action({"name": name, "role": role}, ActionContext(url="/demo/repo/wiki"))
    assert assessment.level == RiskLevel.HIGH
    assert assessment.matched_rule != "benign_docs_link"


async def test_docs_link_without_verb_stays_low() -> None:
    assessment = await check_action(
        {"name": "How do I mirror repositories?", "role": "link"}, ActionContext(url="/demo/repo/settings")
    )
    assert assessment.level == RiskLevel.LOW


# --- 3c: a generic confirm with no detectable dialog context was not HIGH ---


@pytest.mark.parametrize("name", ["Yes", "OK", "Confirm", "Continue"])
async def test_generic_confirm_without_context_pauses(name: str) -> None:
    step = _step(name, "button", f"Click {name}")
    page = PageState(url="/demo/repo/branches", title="Branches", aria_excerpt='- heading "Branches"')

    decision = await PolicyService().check_action(step, page)

    assert decision.verdict == "pause"
    assert decision.reason == "destructive_action"


async def test_generic_confirm_inherits_gitea_dialog_text_before_it() -> None:
    step = _step("Yes", "button", "Confirm in the dialog")
    page = PageState(url="/demo/repo/branches", title="Branches", aria_excerpt=GITEA_DELETE_BRANCH_DIALOG)

    assessment = await check_action(step, page)

    assert assessment.level == RiskLevel.HIGH
    assert assessment.matched_rule == "gitea_dialog_confirm_destructive"


async def test_generic_confirm_with_benign_dialog_is_low_even_if_delete_button_elsewhere() -> None:
    """Over-pausing regression: any "Delete" text anywhere on the page made every Yes pause."""
    excerpt = "\n".join(
        [
            '- link "Delete"',  # an unrelated control elsewhere in the page
            '- heading "Labels"',
            "- paragraph: Apply the default label set to this repository?",
            '- button "No"',
            '- button "Yes"',
        ]
    )
    step = _step("Yes", "button", "Confirm")
    decision = await PolicyService().check_action(
        step, PageState(url="/demo/repo/labels", title="L", aria_excerpt=excerpt)
    )
    assert decision.verdict == "allow"


# --- 3d: missing verbs and cases ---


@pytest.mark.parametrize(
    ("name", "role", "url"),
    [
        ("Remove collaborator", "button", "/demo/repo/settings/collaboration"),
        ("Remove", "button", "/demo/repo/settings/collaboration"),
        ("Regenerate Secret", "button", "/user/settings/applications/oauth2/1"),
        ("Revoke", "button", "/user/settings/applications"),
        ("Revoke token", "button", "/user/settings/applications"),
        ("Make repository private", "checkbox", "/demo/repo/settings"),
        ("Private", "checkbox", "/demo/repo/settings"),
        ("Visibility", "combobox", "/repo/create"),
        ("Public", "radio", "/org/create"),
        ("Change Repository Visibility", "button", "/demo/repo/settings"),
        ("Make Public", "button", "/demo/repo/settings"),
    ],
)
async def test_missing_destructive_cases_are_high(name: str, role: str, url: str) -> None:
    assessment = await check_action({"name": name, "role": role}, ActionContext(url=url))
    assert assessment.level == RiskLevel.HIGH, assessment


async def test_private_dashboard_filter_still_low() -> None:
    assessment = await check_action({"name": "Private", "role": "link"}, ActionContext(url="/"))
    assert assessment.level == RiskLevel.LOW


# --- 5: the typed value leaked into PolicyDecision.message and the logs ---


class _FailingProvider:
    async def generate[M: BaseModel](
        self, *, system: str, prompt: str, schema: type[M], image: bytes | None = None
    ) -> LLMResult[M]:
        raise LLMError("upstream failure")


@pytest.mark.parametrize(
    ("name", "instruction"),
    [
        ("Password", 'Type "S3cr3t-Pa55word!" into Password to reset it'),
        ("Search drafts", 'Type "S3cr3t-Pa55word!" to delete the draft search'),
        ("Token", "Enter S3cr3t-Pa55word! as the token"),
    ],
)
async def test_typed_value_never_in_message_or_logs(
    name: str, instruction: str, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "S3cr3t-Pa55word!"
    step = _step(name, "textbox", instruction, action="fill", value=secret)
    page = PageState(url="/user/settings/account", title="Account")
    service = PolicyService(classifier=LLMClassifier(_FailingProvider()))

    with caplog.at_level(logging.DEBUG):
        decision = await service.check_action(step, page)
        report = await service.assess_plan(PlanDraft(task="Update the account", steps=[step]))

    assert secret not in decision.message
    assert all(secret not in s.reason for s in report.steps)
    assert secret not in caplog.text


# --- 6: over-pausing ---


async def test_fill_value_with_denylist_word_does_not_pause() -> None:
    step = _step(
        "Title",
        "textbox",
        'Type "Delete old docs" as the issue title',
        action="fill",
        value="Delete old docs",
    )
    page = PageState(url="/demo/repo/issues/new", title="New Issue", aria_excerpt='- textbox "Title"')

    decision = await PolicyService().check_action(step, page)

    assert decision.verdict == "allow"


async def test_fill_value_unquoted_in_instruction_does_not_pause() -> None:
    step = _step(
        "Title",
        "textbox",
        "Enter Remove the old branch as the title",
        action="fill",
        value="Remove the old branch",
    )
    decision = await PolicyService().check_action(
        step, PageState(url="/demo/repo/issues/new", title="New Issue")
    )
    assert decision.verdict == "allow"


async def test_fill_into_delete_confirmation_box_still_pauses() -> None:
    """A typed confirmation is a strong signal: the instruction's own verb still counts."""
    step = _step(
        "Repository Name",
        "textbox",
        "Type the repository name to confirm deleting it",
        action="fill",
        value="repo",
    )
    decision = await PolicyService().check_action(
        step, PageState(url="/demo/repo/settings", title="Settings")
    )
    assert decision.verdict == "pause"
