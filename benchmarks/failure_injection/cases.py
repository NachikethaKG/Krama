"""Test case fixtures for failure injection benchmark.

Covers four major UI failure categories:
1. wrong_page: URL does not match expected post-condition regex.
2. missing_element: Target element is absent from DOM / ARIA tree.
3. unexpected_dialog: Unexpected blocking dialog, alert, or modal interrupts flow.
4. wrong_form_value: Form input value fails to match expected submission/state data.

Includes both injected failures (is_failure=True) and passing clean controls (is_failure=False).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.contracts_gen.common_schema import (
    Action,
    ActionType,
    ElementRef,
    ExpectedState,
    FieldValue,
    Target,
)
from app.ports.models import ObservedState
from app.verifier.layered import StepEvidence

from benchmarks.failure_injection.models import FailureCase


def _state(url: str, aria: str = "", title: str = "Gitea") -> ObservedState:
    return ObservedState(
        url=url,
        title=title,
        aria_excerpt=aria,
        captured_at=datetime.now(UTC),
    )


def _evidence(
    action: ActionType = "click",
    target: Target | None = None,
    instruction: str = "Perform action.",
    before: ObservedState | None = None,
    after: ObservedState | None = None,
    value: str | None = None,
) -> StepEvidence:
    return StepEvidence(
        action=Action(type=action, value=value),
        target=target or Target(),
        instruction_text=instruction,
        before=before,
        after=after or _state("/"),
        network=[],
    )


# --------------------------------------------------------------------------------------------------
# 1. WRONG PAGE CASES
# --------------------------------------------------------------------------------------------------

WRONG_PAGE_CASES: list[FailureCase] = [
    FailureCase(
        name="wrong_page_create_repo_fails_stays_on_create",
        failure_type="wrong_page",
        description="Submission failed or errored; page stayed on /repo/create instead of /demo/demo-repo.",
        is_failure=True,
        expected=ExpectedState(url_matches="^/demo/demo-repo$"),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Create Repository"),
            instruction="Click Create Repository button.",
            before=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n  - button "Create Repository"\n',
            ),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n  - paragraph: The repository name is already used.\n',
            ),
        ),
    ),
    FailureCase(
        name="wrong_page_auth_redirect_to_login",
        failure_type="wrong_page",
        description="Session expired; navigation to /settings/profile redirected to /login.",
        is_failure=True,
        expected=ExpectedState(url_matches="^/settings/profile$"),
        evidence=_evidence(
            action="navigate",
            value="/settings/profile",
            instruction="Navigate to profile settings.",
            before=_state("/", '- main:\n  - link "Settings"\n'),
            after=_state(
                "/login",
                '- main:\n  - heading "Sign In" [level=1]\n  - textbox "Username"\n',
            ),
        ),
    ),
    FailureCase(
        name="wrong_page_resource_not_found_404",
        failure_type="wrong_page",
        description="Target issue was deleted or moved; click routed to /404 page.",
        is_failure=True,
        expected=ExpectedState(url_matches="^/demo/demo-repo/issues/1$"),
        evidence=_evidence(
            action="click",
            target=Target(role="link", name="Issue #1"),
            instruction="Click Issue #1.",
            before=_state("/demo/demo-repo/issues", '- main:\n  - link "Issue #1"\n'),
            after=_state(
                "/404", '- main:\n  - heading "Page Not Found (404)" [level=1]\n'
            ),
        ),
    ),
    FailureCase(
        name="clean_page_repo_creation_success",
        failure_type="wrong_page",
        description="Clean step: repository successfully created and browser reached repo page.",
        is_failure=False,
        expected=ExpectedState(url_matches="^/demo/demo-repo$"),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Create Repository"),
            instruction="Click Create Repository button.",
            before=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n  - button "Create Repository"\n',
            ),
            after=_state(
                "/demo/demo-repo",
                '- main:\n  - heading "demo / demo-repo" [level=1]\n  - link "demo-repo"\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_page_settings_navigate",
        failure_type="wrong_page",
        description="Clean step: navigation successfully reached /settings/profile.",
        is_failure=False,
        expected=ExpectedState(url_matches="^/settings/profile$"),
        evidence=_evidence(
            action="navigate",
            value="/settings/profile",
            instruction="Navigate to profile settings.",
            before=_state("/", '- main:\n  - link "Settings"\n'),
            after=_state(
                "/settings/profile",
                '- main:\n  - heading "Profile Settings" [level=1]\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_page_issue_view",
        failure_type="wrong_page",
        description="Clean step: clicked issue link and reached /demo/demo-repo/issues/1.",
        is_failure=False,
        expected=ExpectedState(url_matches="^/demo/demo-repo/issues/1$"),
        evidence=_evidence(
            action="click",
            target=Target(role="link", name="Issue #1"),
            instruction="Click Issue #1 link.",
            before=_state("/demo/demo-repo/issues", '- main:\n  - link "Issue #1"\n'),
            after=_state(
                "/demo/demo-repo/issues/1",
                '- main:\n  - heading "Issue #1: Bug report" [level=1]\n',
            ),
        ),
    ),
]


# --------------------------------------------------------------------------------------------------
# 2. MISSING ELEMENT CASES
# --------------------------------------------------------------------------------------------------

MISSING_ELEMENT_CASES: list[FailureCase] = [
    FailureCase(
        name="missing_element_repo_heading_absent",
        failure_type="missing_element",
        description="Page rendered incomplete or blank; expected repository heading is absent.",
        is_failure=True,
        expected=ExpectedState(
            visible=[ElementRef(role="heading", name="demo / demo-repo")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Create Repository"),
            instruction="Click Create Repository button.",
            before=_state("/repo/create", '- main:\n  - button "Create Repository"\n'),
            after=_state("/demo/demo-repo", "- main:\n  - paragraph: Loading...\n"),
        ),
    ),
    FailureCase(
        name="missing_element_save_button_absent",
        failure_type="missing_element",
        description="Profile editor failed to render action controls; Save Changes button is missing.",
        is_failure=True,
        expected=ExpectedState(
            visible=[ElementRef(role="button", name="Save Changes")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="link", name="Edit Profile"),
            instruction="Click Edit Profile.",
            before=_state("/settings/profile", '- main:\n  - link "Edit Profile"\n'),
            after=_state(
                "/settings/profile/edit", '- main:\n  - textbox "Full Name": Alice\n'
            ),
        ),
    ),
    FailureCase(
        name="missing_element_readme_link_absent",
        failure_type="missing_element",
        description="Repository initialization omitted README; README.md link missing.",
        is_failure=True,
        expected=ExpectedState(
            visible=[ElementRef(role="link", name="README.md")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Initialize Repository"),
            instruction="Click Initialize Repository.",
            before=_state(
                "/demo/demo-repo", '- main:\n  - button "Initialize Repository"\n'
            ),
            after=_state(
                "/demo/demo-repo", '- main:\n  - heading "demo / demo-repo" [level=1]\n'
            ),
        ),
    ),
    FailureCase(
        name="clean_element_repo_heading_present",
        failure_type="missing_element",
        description="Clean step: expected repo heading is present and rendered after action.",
        is_failure=False,
        expected=ExpectedState(
            visible=[ElementRef(role="heading", name="demo / demo-repo")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Create Repository"),
            instruction="Click Create Repository button.",
            before=_state("/repo/create", '- main:\n  - button "Create Repository"\n'),
            after=_state(
                "/demo/demo-repo",
                '- main:\n  - heading "demo / demo-repo" [level=1]\n  - link "demo-repo"\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_element_save_button_present",
        failure_type="missing_element",
        description="Clean step: Save Changes button is rendered and visible.",
        is_failure=False,
        expected=ExpectedState(
            visible=[ElementRef(role="button", name="Save Changes")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="link", name="Edit Profile"),
            instruction="Click Edit Profile.",
            before=_state("/settings/profile", '- main:\n  - link "Edit Profile"\n'),
            after=_state(
                "/settings/profile/edit",
                '- main:\n  - textbox "Full Name": Alice\n  - button "Save Changes"\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_element_readme_link_present",
        failure_type="missing_element",
        description="Clean step: README.md link is present in the repository tree.",
        is_failure=False,
        expected=ExpectedState(
            visible=[ElementRef(role="link", name="README.md")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Initialize Repository"),
            instruction="Click Initialize Repository.",
            before=_state(
                "/demo/demo-repo", '- main:\n  - button "Initialize Repository"\n'
            ),
            after=_state(
                "/demo/demo-repo",
                '- main:\n  - heading "demo / demo-repo" [level=1]\n  - link "README.md"\n',
            ),
        ),
    ),
]


# --------------------------------------------------------------------------------------------------
# 3. UNEXPECTED DIALOG / BLOCKER CASES
# --------------------------------------------------------------------------------------------------

UNEXPECTED_DIALOG_CASES: list[FailureCase] = [
    FailureCase(
        name="unexpected_dialog_confirm_modal_blocks_flow",
        failure_type="unexpected_dialog",
        description="A confirmation modal appeared and interrupted deletion flow.",
        is_failure=True,
        expected=ExpectedState(
            absent=[ElementRef(role="dialog", name="Confirm Delete")],
            visible=[ElementRef(role="heading", name="Repository Deleted")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Delete"),
            instruction="Click Delete button.",
            before=_state("/demo/demo-repo/settings", '- main:\n  - button "Delete"\n'),
            after=_state(
                "/demo/demo-repo/settings",
                '- main:\n  - dialog "Confirm Delete":\n    - button "Yes, Delete"\n',
            ),
        ),
    ),
    FailureCase(
        name="unexpected_dialog_duplicate_name_error_alert",
        failure_type="unexpected_dialog",
        description="Validation error message appeared on page: The repository name is already used.",
        is_failure=True,
        expected=ExpectedState(
            absent=[ElementRef(role="paragraph", name="already used")],
            url_matches="^/demo/demo-repo$",
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Create Repository"),
            instruction="Click Create Repository button.",
            before=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n  - button "Create Repository"\n',
            ),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n  - paragraph: The repository name is already used.\n',
            ),
        ),
    ),
    FailureCase(
        name="unexpected_dialog_session_expired_modal",
        failure_type="unexpected_dialog",
        description="Unexpected 'Session Expired' modal dialog popped up over the active form.",
        is_failure=True,
        expected=ExpectedState(
            absent=[ElementRef(role="dialog", name="Session Expired")],
            visible=[ElementRef(role="button", name="Save Changes")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Save Changes"),
            instruction="Click Save Changes.",
            before=_state("/settings/profile", '- main:\n  - button "Save Changes"\n'),
            after=_state(
                "/settings/profile",
                '- main:\n  - dialog "Session Expired":\n    - button "Log in again"\n',
            ),
        ),
    ),
    FailureCase(
        name="unexpected_dialog_rate_limit_alert",
        failure_type="unexpected_dialog",
        description="Unexpected rate limit alert interrupted API interaction.",
        is_failure=True,
        expected=ExpectedState(
            absent=[ElementRef(role="alert", name="Rate Limit Exceeded")],
            visible=[ElementRef(role="heading", name="Comments")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Post Comment"),
            instruction="Click Post Comment.",
            before=_state(
                "/demo/demo-repo/issues/1", '- main:\n  - button "Post Comment"\n'
            ),
            after=_state(
                "/demo/demo-repo/issues/1",
                '- main:\n  - alert "Rate Limit Exceeded": Slow down\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_dialog_no_confirm_modal",
        failure_type="unexpected_dialog",
        description="Clean step: deletion proceeded without unhandled blocker dialog.",
        is_failure=False,
        expected=ExpectedState(
            absent=[ElementRef(role="dialog", name="Confirm Delete")],
            visible=[ElementRef(role="heading", name="Repository Deleted")],
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Delete"),
            instruction="Click Delete button.",
            before=_state("/demo/demo-repo/settings", '- main:\n  - button "Delete"\n'),
            after=_state(
                "/user/settings/repos",
                '- main:\n  - heading "Repository Deleted" [level=1]\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_dialog_no_error_alert",
        failure_type="unexpected_dialog",
        description="Clean step: create repository completed with no error alert paragraph.",
        is_failure=False,
        expected=ExpectedState(
            absent=[ElementRef(role="paragraph", name="already used")],
            url_matches="^/demo/demo-repo$",
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Create Repository"),
            instruction="Click Create Repository button.",
            before=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n  - button "Create Repository"\n',
            ),
            after=_state(
                "/demo/demo-repo",
                '- main:\n  - heading "demo / demo-repo" [level=1]\n  - link "demo-repo"\n',
            ),
        ),
    ),
]


# --------------------------------------------------------------------------------------------------
# 4. WRONG FORM VALUE CASES
# --------------------------------------------------------------------------------------------------

WRONG_FORM_VALUE_CASES: list[FailureCase] = [
    FailureCase(
        name="wrong_form_value_repo_name_mismatch",
        failure_type="wrong_form_value",
        description="Field contains 'wrong-repo' instead of expected 'demo-repo'.",
        is_failure=True,
        expected=ExpectedState(
            field_values=[
                FieldValue(role="textbox", name="Repository Name", value="demo-repo")
            ],
        ),
        evidence=_evidence(
            action="fill",
            target=Target(role="textbox", name="Repository Name"),
            value="demo-repo",
            instruction="Fill Repository Name with demo-repo.",
            before=_state("/repo/create", '- main:\n  - textbox "Repository Name *"\n'),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": wrong-repo\n',
            ),
        ),
    ),
    FailureCase(
        name="wrong_form_value_empty_textbox",
        failure_type="wrong_form_value",
        description="Field was cleared or failed to register input; value is empty.",
        is_failure=True,
        expected=ExpectedState(
            field_values=[
                FieldValue(role="textbox", name="Repository Name", value="demo-repo")
            ],
        ),
        evidence=_evidence(
            action="fill",
            target=Target(role="textbox", name="Repository Name"),
            value="demo-repo",
            instruction="Fill Repository Name with demo-repo.",
            before=_state("/repo/create", '- main:\n  - textbox "Repository Name *"\n'),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": \n',
            ),
        ),
    ),
    FailureCase(
        name="wrong_form_value_branch_mismatch",
        failure_type="wrong_form_value",
        description="Branch field contains 'master' instead of expected 'main'.",
        is_failure=True,
        expected=ExpectedState(
            field_values=[
                FieldValue(role="textbox", name="Default Branch", value="main")
            ],
        ),
        evidence=_evidence(
            action="fill",
            target=Target(role="textbox", name="Default Branch"),
            value="main",
            instruction="Set default branch to main.",
            before=_state("/repo/create", '- main:\n  - textbox "Default Branch"\n'),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Default Branch": master\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_form_value_repo_name",
        failure_type="wrong_form_value",
        description="Clean step: field value matches expected 'demo-repo' exactly.",
        is_failure=False,
        expected=ExpectedState(
            field_values=[
                FieldValue(role="textbox", name="Repository Name", value="demo-repo")
            ],
        ),
        evidence=_evidence(
            action="fill",
            target=Target(role="textbox", name="Repository Name"),
            value="demo-repo",
            instruction="Fill Repository Name with demo-repo.",
            before=_state("/repo/create", '- main:\n  - textbox "Repository Name *"\n'),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Repository Name *": demo-repo\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_form_value_branch",
        failure_type="wrong_form_value",
        description="Clean step: field value matches expected 'main' exactly.",
        is_failure=False,
        expected=ExpectedState(
            field_values=[
                FieldValue(role="textbox", name="Default Branch", value="main")
            ],
        ),
        evidence=_evidence(
            action="fill",
            target=Target(role="textbox", name="Default Branch"),
            value="main",
            instruction="Set default branch to main.",
            before=_state("/repo/create", '- main:\n  - textbox "Default Branch"\n'),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Default Branch": main\n',
            ),
        ),
    ),
    FailureCase(
        name="clean_form_value_description",
        failure_type="wrong_form_value",
        description="Clean step: description textbox matches filled text.",
        is_failure=False,
        expected=ExpectedState(
            field_values=[
                FieldValue(role="textbox", name="Description", value="Krama Project")
            ],
        ),
        evidence=_evidence(
            action="fill",
            target=Target(role="textbox", name="Description"),
            value="Krama Project",
            instruction="Fill Description with Krama Project.",
            before=_state("/repo/create", '- main:\n  - textbox "Description"\n'),
            after=_state(
                "/repo/create",
                '- main:\n  - textbox "Description": Krama Project\n',
            ),
        ),
    ),
]


ALL_CASES: list[FailureCase] = [
    *WRONG_PAGE_CASES,
    *MISSING_ELEMENT_CASES,
    *UNEXPECTED_DIALOG_CASES,
    *WRONG_FORM_VALUE_CASES,
]
