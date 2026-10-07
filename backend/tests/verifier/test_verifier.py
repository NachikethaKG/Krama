import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.contracts_gen.common_schema import ElementRef, ExpectedState, FieldValue
from app.contracts_gen.plan_schema import PlannedStep
from app.contracts_gen.step_schema import StepVerification
from app.ports.models import ObservedState
from app.verifier import Check, RuleVerifier, ScriptedVerifier, VerificationOutcome, Verifier

# Real ARIA snapshots of `main` on Gitea 1.22.6, captured in the #25 research.
FIXTURES = Path(__file__).parent / "fixtures"
# Real gemini-2.5-flash plan for "create demo-repo" (#25 research), as replayed by the fake LLM.
PLAN = [
    PlannedStep.model_validate(s)
    for s in json.loads(
        (Path(__file__).parents[1] / "llm_fixtures" / "gitea-create-repo-plan.json").read_text(
            encoding="utf-8"
        )
    )["response"]["steps"]
]
TITLE_CREATE = "New Repository - Gitea: Git with a cup of tea"
TITLE_REPO = "demo/demo-repo - demo-repo - Gitea: Git with a cup of tea"

verifier: Verifier = RuleVerifier()


def observed(url: str, title: str, snapshot: str | None) -> ObservedState:
    aria = (FIXTURES / f"{snapshot}.aria.yaml").read_text(encoding="utf-8") if snapshot else ""
    return ObservedState(url=url, title=title, aria_excerpt=aria, captured_at=datetime.now(UTC))


def failed_kinds(outcome: VerificationOutcome) -> list[str]:
    return [c.kind for c in outcome.failures()]


@pytest.mark.parametrize(
    ("seq", "state"),
    [
        (1, observed("/repo/create", TITLE_CREATE, "repo-create-empty")),
        (2, observed("/repo/create", TITLE_CREATE, "repo-create-filled")),
        (3, observed("/repo/create", TITLE_CREATE, "repo-create-filled")),
        (4, observed("/demo/demo-repo", TITLE_REPO, "repo-home")),
    ],
)
def test_real_plan_verifies_against_real_gitea_pages(seq: int, state: ObservedState) -> None:
    outcome = verifier.verify(PLAN[seq - 1].expected_state, state)

    assert outcome.verified, outcome.checks
    assert outcome.verification.confidence == 1.0


def test_wrong_page_is_detected_duplicate_repo_name() -> None:
    # Same name twice: Gitea stays on /repo/create and only shows a paragraph; "page loaded" would pass.
    outcome = verifier.verify(
        PLAN[3].expected_state, observed("/repo/create", TITLE_CREATE, "repo-create-duplicate")
    )

    assert outcome.verification.result == "failed"
    assert set(failed_kinds(outcome)) == {"url_matches", "title_contains"}
    url_check = next(c for c in outcome.checks if c.kind == "url_matches")
    assert url_check.detail == "path is '/repo/create'"


def test_absent_error_message_is_matched_by_its_text() -> None:
    expected = ExpectedState(absent=[ElementRef(role="paragraph", name="already used")])

    ok = verifier.verify(expected, observed("/repo/create", TITLE_CREATE, "repo-create-filled"))
    bad = verifier.verify(expected, observed("/repo/create", TITLE_CREATE, "repo-create-duplicate"))

    assert ok.verified
    assert failed_kinds(bad) == ["absent"]
    assert "The repository name is already used." in bad.failures()[0].detail


def test_unchecked_box_fails() -> None:
    outcome = verifier.verify(
        PLAN[2].expected_state, observed("/repo/create", TITLE_CREATE, "repo-create-empty")
    )

    assert failed_kinds(outcome) == ["checked"]
    assert outcome.failures()[0].detail == "not checked"


def test_wrong_field_value_fails() -> None:
    expected = ExpectedState(field_values=[FieldValue(role="textbox", name="Repository Name", value="other")])

    outcome = verifier.verify(expected, observed("/repo/create", TITLE_CREATE, "repo-create-filled"))

    assert failed_kinds(outcome) == ["field_value"]
    assert outcome.failures()[0].detail == "value is 'demo-repo'"


def test_missing_element_fails_and_name_match_is_case_insensitive_substring() -> None:
    present = ExpectedState(visible=[ElementRef(role="button", name="create repository")])
    missing = ExpectedState(visible=[ElementRef(role="button", name="Delete Repository")])
    state = observed("/repo/create", TITLE_CREATE, "repo-create-empty")

    assert verifier.verify(present, state).verified
    assert failed_kinds(verifier.verify(missing, state)) == ["visible"]


def test_role_must_match_exactly() -> None:
    # "New Repository" is a heading on this page, not a button.
    expected = ExpectedState(visible=[ElementRef(role="button", name="New Repository")])

    outcome = verifier.verify(expected, observed("/repo/create", TITLE_CREATE, "repo-create-empty"))

    assert not outcome.verified


def test_methods_list_every_signal_used() -> None:
    outcome = verifier.verify(PLAN[3].expected_state, observed("/demo/demo-repo", TITLE_REPO, "repo-home"))
    aria_too = verifier.verify(
        PLAN[0].expected_state, observed("/repo/create", TITLE_CREATE, "repo-create-empty")
    )

    assert outcome.verification.method == ["url", "dom"]
    assert aria_too.verification.method == ["url", "aria"]


def test_without_aria_snapshot_aria_checks_are_skipped_not_passed() -> None:
    outcome = verifier.verify(PLAN[0].expected_state, observed("/repo/create", TITLE_CREATE, None))

    assert outcome.verification.result == "skipped"
    assert outcome.verification.confidence == 0.5
    assert {c.passed for c in outcome.checks if c.kind == "visible"} == {None}


def test_failure_wins_over_missing_snapshot() -> None:
    outcome = verifier.verify(PLAN[0].expected_state, observed("/", "Dashboard", None))

    assert outcome.verification.result == "failed"


def test_url_regex_searches_the_path_only() -> None:
    state = observed("/demo/demo-repo", TITLE_REPO, None)

    assert verifier.verify(ExpectedState(url_matches="^/demo/demo-repo$"), state).verified
    assert not verifier.verify(ExpectedState(url_matches="^/demo$"), state).verified
    bad = verifier.verify(ExpectedState(url_matches="^/demo/(oops$"), state)
    assert bad.failures()[0].detail.startswith("invalid regex")


def test_empty_expected_state_is_skipped() -> None:
    outcome = verifier.verify(ExpectedState(), observed("/", "Dashboard", None))

    assert outcome.verification.result == "skipped"


def test_result_is_a_contract_step_verification() -> None:
    outcome = verifier.verify(PLAN[3].expected_state, observed("/demo/demo-repo", TITLE_REPO, "repo-home"))

    data = outcome.verification.model_dump(mode="json")
    assert StepVerification.model_validate(data) == outcome.verification
    assert data == {"result": "verified", "method": ["url", "dom"], "confidence": 1.0}


def test_scripted_verifier_replays_outcomes() -> None:
    canned = VerificationOutcome(
        verification=StepVerification(result="failed", method=["url"], confidence=1.0),
        checks=[Check(kind="url_matches", expected="^/x$", passed=False, detail="path is '/'")],
    )
    scripted: Verifier = ScriptedVerifier([canned])

    assert scripted.verify(ExpectedState(url_matches="^/x$"), observed("/", "t", None)) == canned
    with pytest.raises(AssertionError):
        scripted.verify(ExpectedState(url_matches="^/x$"), observed("/", "t", None))
