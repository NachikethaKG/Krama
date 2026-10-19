"""A generic confirm inside a dialog with a form field (#78): Gitea's "Create new branch" dialog.

The observer puts an open dialog under a `- dialog:` line. Inside it, the policy skips the dialog's form
fields to reach the dialog's text; outside a dialog, a field right before a confirm still means "no context".
"""

import pytest

from app.contracts_gen.common_schema import Action, Target
from app.policy.models import RiskLevel
from app.policy.risk import check_action
from app.policy.service import PolicyService
from app.ports.models import PageState, StepRef

pytestmark = pytest.mark.anyio

MAIN = '- heading "Branches" [level=4]\n- button "Create new branch from \\"main\\""'


def confirm(instruction: str = "In the dialog, click Confirm") -> StepRef:
    return StepRef(seq=4, action=Action(type="click"), target=Target(role="button", name="Confirm"),
                   instruction_text=instruction)  # fmt: skip


def page(*dialog: str) -> PageState:
    excerpt = "\n".join([MAIN, "- dialog:", *(f"  {line}" for line in dialog)])
    return PageState(url="/demo/repo/branches", title="Branches", aria_excerpt=excerpt)


async def test_a_benign_dialog_with_a_field_before_its_confirm_is_low() -> None:
    gitea_create_branch = page(
        '- text: "Create new branch Create branch from branch: main Branch Name *"',
        '- textbox "Branch Name *": feature-docs',
        '- button "Cancel"',
        '- button "Confirm"',
    )

    decision = await PolicyService().check_action(confirm(), gitea_create_branch)
    assessment = await check_action(confirm(), gitea_create_branch)

    assert decision.verdict == "allow"
    assert (assessment.level, assessment.matched_rule) == (RiskLevel.LOW, "generic_confirm_benign_context")


async def test_a_destructive_dialog_with_a_field_before_its_confirm_still_pauses() -> None:
    # Gitea's delete-repository dialog asks you to type the name before confirming.
    delete_repo = page(
        "- text: Delete This Repository",
        "- paragraph: This operation will permanently delete the repository. It CANNOT be undone.",
        '- textbox "Repository Name": demo-repo',
        '- button "Confirm"',
    )

    decision = await PolicyService().check_action(confirm(), delete_repo)

    assert decision.verdict == "pause" and decision.reason == "destructive_action"


async def test_a_titled_dialog_without_other_text_uses_its_title() -> None:
    titled = PageState(
        url="/x",
        title="X",
        aria_excerpt='- dialog "Rename label":\n  - textbox "Name": bugs\n  - button "Confirm"',
    )

    assessment = await check_action(confirm(), titled)

    assert assessment.level == RiskLevel.LOW


async def test_the_scan_never_crosses_the_dialog_edge_into_the_page() -> None:
    # Text above the dialog belongs to the page, not to the dialog: it must not make the confirm look benign.
    excerpt = "\n".join(
        ["- paragraph: Welcome to your dashboard", "- dialog:", '  - textbox "Code"', '  - button "Confirm"']
    )
    assessment = await check_action(confirm(), PageState(url="/x", title="X", aria_excerpt=excerpt))

    assert assessment.matched_rule == "generic_confirm_without_context" and assessment.level == RiskLevel.HIGH


async def test_outside_a_dialog_a_field_before_the_confirm_still_means_no_context() -> None:
    excerpt = "\n".join(["- paragraph: Apply the change?", '- textbox "Code"', '- button "Confirm"'])
    assessment = await check_action(confirm(), PageState(url="/x", title="X", aria_excerpt=excerpt))

    assert assessment.matched_rule == "generic_confirm_without_context" and assessment.level == RiskLevel.HIGH
