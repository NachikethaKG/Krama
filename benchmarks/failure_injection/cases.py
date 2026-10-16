"""Test case fixtures for failure injection benchmark.

Covers five UI failure categories:
1. wrong_page: URL does not match expected post-condition regex.
2. missing_element: Target element is absent from DOM / ARIA tree.
3. unexpected_dialog: Unexpected blocking dialog, alert, or modal interrupts flow.
4. wrong_form_value: Form input value fails to match expected submission/state data.
5. weak_signal: the step "ran" but did nothing, and the expectation is too weak to notice
   (docs/research/phase-1-together-verified-definition.md, weak-signal table). Nothing in the after-state
   contradicts the expectation, so a rules-only verifier says `verified`; the correct answer is `skipped`
   (no effect signal: pause for a human), or `failed` when the network shows the server refused.

Includes both injected failures (is_failure=True) and passing clean controls (is_failure=False). Every case
declares `expected_result`, the answer a correct verifier gives.
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
from app.verifier.layered import NetworkCall, StepEvidence

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
    network: list[NetworkCall] | None = None,
) -> StepEvidence:
    return StepEvidence(
        action=Action(type=action, value=value),
        target=target or Target(),
        instruction_text=instruction,
        before=before,
        after=after or _state("/"),
        network=network or [],
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="verified",
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
        expected_result="verified",
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
        expected_result="verified",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="verified",
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
        expected_result="verified",
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
        expected_result="verified",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="verified",
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
        expected_result="verified",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="failed",
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
        expected_result="verified",
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
        expected_result="verified",
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
        expected_result="verified",
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


# --------------------------------------------------------------------------------------------------
# 5. WEAK SIGNAL CASES (the step ran, nothing contradicts a weak expectation, yet nothing happened)
# --------------------------------------------------------------------------------------------------

_CREATE = "/repo/create"
_CREATE_BUTTON = Target(role="button", name="Create Repository")
_CREATE_FORM = (
    '- main:\n  - textbox "Repository Name *": demo-repo\n'
    '  - button "Create Repository"\n'
)
# Real Gitea refuses a duplicate name by re-rendering the same form with an error paragraph.
_CREATE_REFUSED = (
    "- main:\n  - paragraph: The repository name is already used.\n"
    '  - textbox "Repository Name *": demo-repo\n  - button "Create Repository"\n'
)
_ISSUE = "/demo/demo-repo/issues/1"
_ISSUE_PAGE = (
    '- main:\n  - heading "Issue #1: Bug report" [level=1]\n'
    '  - heading "Comments" [level=2]\n  - textbox "Comment": LGTM\n'
    '  - button "Post Comment"\n'
)


def _post(status: int | None, resource_type: str, path: str = _CREATE) -> NetworkCall:
    return NetworkCall(
        method="POST", path=path, status=status, resource_type=resource_type
    )


WEAK_SIGNAL_CASES: list[FailureCase] = [
    FailureCase(
        name="weak_title_only_noop_click",
        failure_type="weak_signal",
        description="Click did nothing; the only expectation is title_contains 'Gitea', "
        "which is true on every Gitea page.",
        is_failure=True,
        expected_result="skipped",
        expected=ExpectedState(title_contains="Gitea"),
        evidence=_evidence(
            action="click",
            target=_CREATE_BUTTON,
            instruction="Click Create Repository button.",
            before=_state(_CREATE, _CREATE_FORM),
            after=_state(_CREATE, _CREATE_FORM),
        ),
    ),
    FailureCase(
        name="weak_visible_already_present_before_click",
        failure_type="weak_signal",
        description="Duplicate name refused; expectation is the 'Create Repository' button "
        "being visible, but it was already there before the click.",
        is_failure=True,
        expected_result="skipped",
        expected=ExpectedState(
            visible=[ElementRef(role="button", name="Create Repository")]
        ),
        evidence=_evidence(
            action="click",
            target=_CREATE_BUTTON,
            instruction="Click Create Repository button.",
            before=_state(_CREATE, _CREATE_FORM),
            after=_state(_CREATE, _CREATE_REFUSED),
        ),
    ),
    FailureCase(
        name="weak_vacuous_absent_wrong_role",
        failure_type="weak_signal",
        description="Duplicate name refused; the only expectation is 'absent' of the error "
        "with role 'text', but the error is a paragraph, so 'absent' passes vacuously.",
        is_failure=True,
        expected_result="skipped",
        expected=ExpectedState(
            absent=[ElementRef(role="text", name="The repository name is already used")]
        ),
        evidence=_evidence(
            action="click",
            target=_CREATE_BUTTON,
            instruction="Click Create Repository button.",
            before=_state(_CREATE, _CREATE_FORM),
            after=_state(_CREATE, _CREATE_REFUSED),
        ),
    ),
    FailureCase(
        name="weak_click_no_effect_url_already_true",
        failure_type="weak_signal",
        description="Click on 'Watch' had no effect at all (no request, page unchanged); the "
        "expected URL was already the current URL before the click.",
        is_failure=True,
        expected_result="skipped",
        expected=ExpectedState(url_matches="^/demo/demo-repo$"),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Watch"),
            instruction="Click Watch.",
            before=_state("/demo/demo-repo", '- main:\n  - button "Watch"\n'),
            after=_state("/demo/demo-repo", '- main:\n  - button "Watch"\n'),
        ),
    ),
    FailureCase(
        name="weak_duplicate_name_document_post_200",
        failure_type="weak_signal",
        description="Hard duplicate-name case: page stays on /repo/create with the error "
        "paragraph, the form POST got 200 (Gitea re-renders a refused form with 200, a real "
        "create redirects), and the expectations are weak (title + field already filled).",
        is_failure=True,
        expected_result="skipped",
        expected=ExpectedState(
            title_contains="Gitea",
            visible=[ElementRef(role="textbox", name="Repository Name")],
        ),
        evidence=_evidence(
            action="click",
            target=_CREATE_BUTTON,
            instruction="Click Create Repository button.",
            before=_state(_CREATE, _CREATE_FORM),
            after=_state(_CREATE, _CREATE_REFUSED),
            network=[_post(200, "document")],
        ),
    ),
    FailureCase(
        name="weak_xhr_post_server_error",
        failure_type="weak_signal",
        description="Posting a comment: the fetch POST answered 500, the page looks unchanged "
        "and the expectation (Comments heading) was already true.",
        is_failure=True,
        expected_result="failed",
        expected=ExpectedState(visible=[ElementRef(role="heading", name="Comments")]),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Post Comment"),
            instruction="Click Post Comment.",
            before=_state(_ISSUE, _ISSUE_PAGE),
            after=_state(_ISSUE, _ISSUE_PAGE),
            network=[_post(500, "fetch", f"{_ISSUE}/comments")],
        ),
    ),
    FailureCase(
        name="weak_document_post_no_response",
        failure_type="weak_signal",
        description="Form POST got no response (connection dropped); the page still shows "
        "the form and the expectation is title-only.",
        is_failure=True,
        expected_result="failed",
        expected=ExpectedState(title_contains="Gitea"),
        evidence=_evidence(
            action="click",
            target=_CREATE_BUTTON,
            instruction="Click Create Repository button.",
            before=_state(_CREATE, _CREATE_FORM),
            after=_state(_CREATE, _CREATE_FORM),
            network=[_post(None, "document")],
        ),
    ),
    FailureCase(
        name="clean_weak_create_redirect_303",
        failure_type="weak_signal",
        description="Clean step: form POST answered 303 and the URL changed to the new repo; "
        "expectations are title + URL.",
        is_failure=False,
        expected_result="verified",
        expected=ExpectedState(title_contains="Gitea", url_matches="^/demo/demo-repo$"),
        evidence=_evidence(
            action="click",
            target=_CREATE_BUTTON,
            instruction="Click Create Repository button.",
            before=_state(_CREATE, _CREATE_FORM),
            after=_state(
                "/demo/demo-repo", '- main:\n  - heading "demo / demo-repo" [level=1]\n'
            ),
            network=[_post(303, "document")],
        ),
    ),
    FailureCase(
        name="clean_weak_xhr_comment_accepted",
        failure_type="weak_signal",
        description="Clean step: fetch POST answered 201; the only page expectation is "
        "'absent' of a rate-limit alert, the network call is the effect signal.",
        is_failure=False,
        expected_result="verified",
        expected=ExpectedState(
            absent=[ElementRef(role="alert", name="Rate Limit Exceeded")]
        ),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Post Comment"),
            instruction="Click Post Comment.",
            before=_state(_ISSUE, _ISSUE_PAGE),
            after=_state(_ISSUE, _ISSUE_PAGE + "  - paragraph: LGTM\n"),
            network=[_post(201, "fetch", f"{_ISSUE}/comments")],
        ),
    ),
    FailureCase(
        name="clean_weak_watch_toggles_to_unwatch",
        failure_type="weak_signal",
        description="Clean step: clicking Watch made a new 'Unwatch' button appear "
        "(an element that was not present before).",
        is_failure=False,
        expected_result="verified",
        expected=ExpectedState(visible=[ElementRef(role="button", name="Unwatch")]),
        evidence=_evidence(
            action="click",
            target=Target(role="button", name="Watch"),
            instruction="Click Watch.",
            before=_state("/demo/demo-repo", '- main:\n  - button "Watch"\n'),
            after=_state("/demo/demo-repo", '- main:\n  - button "Unwatch"\n'),
        ),
    ),
]


ALL_CASES: list[FailureCase] = [
    *WRONG_PAGE_CASES,
    *MISSING_ELEMENT_CASES,
    *UNEXPECTED_DIALOG_CASES,
    *WRONG_FORM_VALUE_CASES,
    *WEAK_SIGNAL_CASES,
]
