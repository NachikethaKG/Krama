"""Unit and integration tests for the failure-injection benchmark harness."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Literal

import pytest
from app.contracts_gen.common_schema import (
    ExpectedState,
)
from app.contracts_gen.step_schema import (
    StepVerification,
)
from app.verifier.layered import (
    LayeredVerifier,
    StepEvidence,
)
from app.verifier.verifier import (
    Check,
    RuleVerifier,
    VerificationOutcome,
)

from benchmarks.failure_injection.cases import (
    ALL_CASES,
    MISSING_ELEMENT_CASES,
    UNEXPECTED_DIALOG_CASES,
    WEAK_SIGNAL_CASES,
    WRONG_FORM_VALUE_CASES,
    WRONG_PAGE_CASES,
)
from benchmarks.failure_injection.evaluator import FailureInjectionEvaluator
from benchmarks.failure_injection.models import (
    AccuracyReport,
    FailureCase,
    FailureType,
)
from benchmarks.failure_injection.reporter import FailureInjectionReporter
from benchmarks.failure_injection.runner import (
    run_benchmark,
    select_cases,
)

pytestmark = pytest.mark.anyio


class FixedVerifier:
    """Mock verifier that always returns the same result."""

    def __init__(self, result: Literal["verified", "failed", "skipped"]) -> None:
        self.result = result

    def verify(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> VerificationOutcome:
        return VerificationOutcome(
            verification=StepVerification(
                result=self.result,
                method=["url"],
                confidence=1.0 if self.result != "skipped" else 0.5,
            ),
            checks=[
                Check(
                    kind="url_matches",
                    expected="test",
                    passed=self.result != "failed",
                    detail=f"forced {self.result}",
                )
            ],
        )


class CrashingVerifier:
    """Mock verifier that throws an unhandled exception."""

    def verify(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> VerificationOutcome:
        raise RuntimeError("Verifier internal engine malfunction")


INJECTED = [c for c in ALL_CASES if c.is_failure]
CONTROLS = [c for c in ALL_CASES if not c.is_failure]
WEAK_INJECTED = [c for c in WEAK_SIGNAL_CASES if c.is_failure]


# --------------------------------------------------------------------------------------------------
# Test cases integrity
# --------------------------------------------------------------------------------------------------


def test_cases_suite_contains_all_failure_modes() -> None:
    types: set[FailureType] = {c.failure_type for c in ALL_CASES}
    assert types == {
        "wrong_page",
        "missing_element",
        "unexpected_dialog",
        "wrong_form_value",
        "weak_signal",
    }


def test_case_names_unique() -> None:
    names = [c.name for c in ALL_CASES]
    assert len(names) == len(set(names))


def test_each_category_has_both_injected_failures_and_controls() -> None:
    categories = [
        WRONG_PAGE_CASES,
        MISSING_ELEMENT_CASES,
        UNEXPECTED_DIALOG_CASES,
        WRONG_FORM_VALUE_CASES,
        WEAK_SIGNAL_CASES,
    ]
    for cat in categories:
        injected = [c for c in cat if c.is_failure]
        controls = [c for c in cat if not c.is_failure]
        assert len(injected) >= 3, (
            f"Expected at least 3 injected failures in {cat[0].failure_type}"
        )
        assert len(controls) >= 2, (
            f"Expected at least 2 clean controls in {cat[0].failure_type}"
        )


def test_case_models_valid() -> None:
    for case in ALL_CASES:
        assert case.name
        assert case.description
        assert isinstance(case.expected, ExpectedState)
        assert isinstance(case.evidence, StepEvidence)
        assert isinstance(case.is_failure, bool)
        assert case.expected_result in ("verified", "failed", "skipped")


def test_weak_signal_cases_cover_the_research_table() -> None:
    """The weak-signal table in docs/research/phase-1-together-verified-definition.md."""
    by_name = {c.name: c for c in WEAK_SIGNAL_CASES}
    title_only = by_name["weak_title_only_noop_click"]
    assert title_only.expected.title_contains == "Gitea"
    assert title_only.evidence.before == title_only.evidence.after or (
        title_only.evidence.before is not None
        and title_only.evidence.before.aria_excerpt
        == title_only.evidence.after.aria_excerpt
    )
    already = by_name["weak_visible_already_present_before_click"]
    assert already.evidence.before is not None
    assert "Create Repository" in already.evidence.before.aria_excerpt
    vacuous = by_name["weak_vacuous_absent_wrong_role"]
    assert vacuous.expected.absent and vacuous.expected.absent[0].role == "text"
    assert "paragraph: The repository name" in vacuous.evidence.after.aria_excerpt
    hard = by_name["weak_duplicate_name_document_post_200"]
    assert hard.evidence.after.url == "/repo/create"
    assert [(n.method, n.status, n.resource_type) for n in hard.evidence.network] == [
        ("POST", 200, "document")
    ]
    for name in (
        "weak_title_only_noop_click",
        "weak_visible_already_present_before_click",
        "weak_vacuous_absent_wrong_role",
        "weak_click_no_effect_url_already_true",
        "weak_duplicate_name_document_post_200",
    ):
        assert by_name[name].expected_result == "skipped"


def test_case_rejects_inconsistent_expected_result() -> None:
    base = WEAK_SIGNAL_CASES[0]
    with pytest.raises(ValueError, match="never expect 'verified'"):
        FailureCase(
            **{
                **base.model_dump(exclude={"expected", "evidence"}),
                "expected_result": "verified",
            },
            expected=base.expected,
            evidence=base.evidence,
        )
    with pytest.raises(ValueError, match="must expect 'verified'"):
        FailureCase(
            **{
                **base.model_dump(exclude={"expected", "evidence"}),
                "is_failure": False,
                "expected_result": "skipped",
            },
            expected=base.expected,
            evidence=base.evidence,
        )


# --------------------------------------------------------------------------------------------------
# LayeredVerifier vs RuleVerifier: per-case expected outcomes
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.name)
async def test_layered_verifier_gives_each_case_its_expected_result(
    case: FailureCase,
) -> None:
    result = await FailureInjectionEvaluator(LayeredVerifier()).evaluate_case(case)
    assert result.outcome_result == case.expected_result
    assert result.matches_expected is True


async def test_evaluator_with_layered_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=LayeredVerifier())
    report = await evaluator.evaluate_all(ALL_CASES)

    assert report.total_cases == len(ALL_CASES)
    assert report.errors == 0
    assert report.expected_mismatches == 0
    assert report.silently_passed == 0
    assert report.silently_passed_rate == 0.0
    assert report.false_negatives == 0
    assert report.detection_accuracy == 1.0
    assert report.false_alarm_rate == 0.0
    assert report.needless_pause_rate == 0.0
    assert report.paused_failures == sum(
        1 for c in INJECTED if c.expected_result == "skipped"
    )
    assert report.true_positives == sum(
        1 for c in INJECTED if c.expected_result == "failed"
    )
    assert report.hard_detection_rate < 1.0  # weak signals are paused, not failed

    weak = report.by_type["weak_signal"]
    assert weak.injected_outcomes.verified == 0
    assert weak.injected_outcomes.skipped == 5
    assert weak.injected_outcomes.failed == 2
    assert weak.control_outcomes.verified == weak.clean_controls


async def test_rule_verifier_silently_passes_the_weak_signal_cases() -> None:
    """The benchmark has teeth: the rules layer alone verifies every weak-signal failure."""
    report = await FailureInjectionEvaluator(RuleVerifier()).evaluate_all(ALL_CASES)

    silently_passed = {
        r.case_name
        for r in report.cases
        if r.is_failure and r.outcome_result == "verified"
    }
    assert {c.name for c in WEAK_INJECTED} <= silently_passed
    assert report.silently_passed >= len(WEAK_INJECTED)
    assert report.silently_passed_rate > 0.0
    assert report.by_type["weak_signal"].silently_passed_rate == 1.0
    assert report.expected_mismatches >= len(WEAK_INJECTED)


async def test_layered_and_rule_reports_differ() -> None:
    layered = await FailureInjectionEvaluator(LayeredVerifier()).evaluate_all(ALL_CASES)
    rule = await FailureInjectionEvaluator(RuleVerifier()).evaluate_all(ALL_CASES)
    assert layered.silently_passed == 0 < rule.silently_passed
    assert layered.detection_accuracy > rule.detection_accuracy
    assert [r.outcome_result for r in layered.cases] != [
        r.outcome_result for r in rule.cases
    ]


# --------------------------------------------------------------------------------------------------
# Evaluator scoring: false alarms, misses, skipped, exceptions, empty denominators
# --------------------------------------------------------------------------------------------------


async def test_evaluator_detects_false_alarms_with_always_fail_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=FixedVerifier("failed"))
    report = await evaluator.evaluate_all(ALL_CASES)

    assert report.true_positives == report.injected_failures
    assert report.false_negatives == 0
    assert report.detection_accuracy == 1.0
    assert report.hard_detection_rate == 1.0

    assert report.false_positives == report.clean_controls
    assert report.true_negatives == 0
    assert report.false_alarm_rate == 1.0


async def test_evaluator_detects_missed_failures_with_always_pass_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=FixedVerifier("verified"))
    report = await evaluator.evaluate_all(ALL_CASES)

    assert report.true_positives == 0
    assert report.false_negatives == report.injected_failures
    assert report.silently_passed == report.injected_failures
    assert report.silently_passed_rate == 1.0
    assert report.detection_accuracy == 0.0

    assert report.false_positives == 0
    assert report.true_negatives == report.clean_controls
    assert report.false_alarm_rate == 0.0


async def test_skipped_is_its_own_outcome() -> None:
    """skipped on an injected case = caught for a human; on a control = needless pause."""
    report = await FailureInjectionEvaluator(FixedVerifier("skipped")).evaluate_all(
        ALL_CASES
    )

    assert report.paused_failures == report.injected_failures
    assert report.true_positives == 0  # not counted as a hard 'failed'
    assert report.silently_passed == 0
    assert report.detection_accuracy == 1.0  # not silently passed
    assert report.hard_detection_rate == 0.0

    assert report.needless_pauses == report.clean_controls
    assert report.needless_pause_rate == 1.0
    assert report.false_positives == 0
    assert report.false_alarm_rate == 0.0
    for r in report.cases:
        assert r.classification == ("TP_PAUSED" if r.is_failure else "FP_PAUSED")


async def test_evaluator_counts_crashes_as_misses_and_false_alarms() -> None:
    evaluator = FailureInjectionEvaluator(verifier=CrashingVerifier())
    report = await evaluator.evaluate_all(ALL_CASES)

    assert report.total_cases == len(ALL_CASES)
    assert report.errors == len(ALL_CASES)
    for c in report.cases:
        assert c.outcome_result == "error"
        assert c.classification == ("FN" if c.is_failure else "FP")
        assert c.matches_expected is False
        assert c.error_message is not None
        assert "Verifier internal engine malfunction" in c.error_message

    # A verifier that crashes on everything must NOT look perfect.
    assert report.injected_failures == len(INJECTED)
    assert report.clean_controls == len(CONTROLS)
    assert report.false_negatives == len(INJECTED)
    assert report.detection_accuracy == 0.0
    assert report.false_positives == len(CONTROLS)
    assert report.false_alarm_rate == 1.0
    assert report.silently_passed == 0  # a crash is a miss, not a 'verified'
    for m in report.by_type.values():
        assert m.recall == 0.0
        assert m.injected_outcomes.error == m.injected_failures
        assert m.control_outcomes.error == m.clean_controls


async def test_rates_default_to_zero_when_nothing_to_count() -> None:
    evaluator = FailureInjectionEvaluator(verifier=LayeredVerifier())
    empty = await evaluator.evaluate_all([])
    assert empty.detection_accuracy == 0.0
    assert empty.hard_detection_rate == 0.0
    assert empty.false_alarm_rate == 0.0
    controls_only = await evaluator.evaluate_all(CONTROLS)
    assert controls_only.injected_failures == 0
    assert controls_only.detection_accuracy == 0.0
    for m in controls_only.by_type.values():
        assert m.recall == 0.0


def test_evaluator_sync_run_method() -> None:
    evaluator = FailureInjectionEvaluator(verifier=RuleVerifier())
    cases = ALL_CASES[:4]
    report = evaluator.run(cases)
    assert report.total_cases == 4
    assert report.errors == 0


# --------------------------------------------------------------------------------------------------
# Reporter tests
# --------------------------------------------------------------------------------------------------


def test_reporter_render_output() -> None:
    evaluator = FailureInjectionEvaluator(verifier=RuleVerifier())
    report = evaluator.run(ALL_CASES[:4])

    buf = io.StringIO()
    reporter = FailureInjectionReporter(stream=buf)
    saved_path = Path("/tmp/verifier-accuracy.json")
    reporter.render(report, saved_path=saved_path)

    out = buf.getvalue()
    assert "VERIFIER FAILURE-INJECTION BENCHMARK REPORT" in out
    assert "Detection Accuracy (Recall):" in out
    assert "False Alarm Rate (FP Rate):" in out
    assert "PER-FAILURE-TYPE BREAKDOWN:" in out
    assert "CASE EVALUATION DETAILS:" in out
    assert "Report saved to:" in out


def test_reporter_save_report(tmp_path: Path) -> None:
    evaluator = FailureInjectionEvaluator(verifier=RuleVerifier())
    report = evaluator.run(ALL_CASES[:2])

    reporter = FailureInjectionReporter()
    saved = reporter.save_report(report, results_dir=tmp_path)

    assert saved.exists()
    assert saved.name.startswith("verifier-accuracy-")
    assert saved.suffix == ".json"

    loaded = AccuracyReport.model_validate_json(saved.read_text(encoding="utf-8"))
    assert loaded.total_cases == 2
    assert loaded.verifier_name == "RuleVerifier"


# --------------------------------------------------------------------------------------------------
# Runner CLI tests
# --------------------------------------------------------------------------------------------------


def test_runner_filter_cases() -> None:
    cases = select_cases("wrong_page")
    assert len(cases) == len(WRONG_PAGE_CASES)
    assert all(c.failure_type == "wrong_page" for c in cases)

    all_c = select_cases(None)
    assert len(all_c) == len(ALL_CASES)


def test_runner_cli_execution_success(tmp_path: Path) -> None:
    code = run_benchmark(
        [
            "--verifier",
            "rule",
            "--filter-type",
            "wrong_page",
            "--results-dir",
            str(tmp_path),
            "--min-accuracy",
            "0.9",
            "--max-false-alarm",
            "0.1",
        ]
    )
    assert code == 0

    saved_files = list(tmp_path.glob("verifier-accuracy-*.json"))
    assert len(saved_files) == 1


def test_runner_cli_threshold_failure_min_accuracy() -> None:
    # Requires 105% accuracy, which is impossible -> should exit with code 1
    code = run_benchmark(
        [
            "--verifier",
            "rule",
            "--filter-type",
            "wrong_page",
            "--no-save",
            "--min-accuracy",
            "1.05",
        ]
    )
    assert code == 1


def test_runner_cli_threshold_failure_max_false_alarm() -> None:
    # Requires < -0.1 false alarm rate, which is impossible -> should exit with code 1
    code = run_benchmark(
        [
            "--verifier",
            "rule",
            "--filter-type",
            "wrong_page",
            "--no-save",
            "--max-false-alarm",
            "-0.1",
        ]
    )
    assert code == 1


def test_runner_full_suite_passes_with_layered_verifier() -> None:
    assert run_benchmark(["--verifier", "layered", "--no-save"]) == 0


def test_runner_exits_non_zero_when_rule_verifier_silently_passes() -> None:
    assert run_benchmark(["--verifier", "rule", "--no-save"]) == 1
    # The silent-pass gate can be relaxed explicitly.
    assert (
        run_benchmark(
            ["--verifier", "rule", "--no-save", "--max-silently-passed", "1.0"]
        )
        == 0
    )


def test_runner_exits_non_zero_on_verifier_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import benchmarks.failure_injection.runner as runner_mod

    monkeypatch.setattr(runner_mod, "LayeredVerifier", CrashingVerifier)
    assert run_benchmark(["--verifier", "layered", "--no-save"]) == 1


def test_reporter_shows_skipped_and_silent_pass_columns() -> None:
    report = FailureInjectionEvaluator(RuleVerifier()).run(WEAK_SIGNAL_CASES)
    buf = io.StringIO()
    FailureInjectionReporter(stream=buf).render(report)
    out = buf.getvalue()
    assert "Silently Passed (must be 0):" in out
    assert "Needless Pause Rate:" in out
    assert "!! expected skipped, got verified" in out
