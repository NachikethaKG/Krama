"""Unit and integration tests for the failure-injection benchmark harness."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from app.contracts_gen.common_schema import (  # type: ignore[import-untyped]
    ExpectedState,
)
from app.contracts_gen.step_schema import (  # type: ignore[import-untyped]
    StepVerification,
)
from app.verifier.layered import (  # type: ignore[import-untyped]
    LayeredVerifier,
    StepEvidence,
)
from app.verifier.verifier import (  # type: ignore[import-untyped]
    Check,
    RuleVerifier,
    VerificationOutcome,
)

from benchmarks.failure_injection.cases import (
    ALL_CASES,
    MISSING_ELEMENT_CASES,
    UNEXPECTED_DIALOG_CASES,
    WRONG_FORM_VALUE_CASES,
    WRONG_PAGE_CASES,
)
from benchmarks.failure_injection.evaluator import FailureInjectionEvaluator
from benchmarks.failure_injection.models import (
    AccuracyReport,
    FailureType,
)
from benchmarks.failure_injection.reporter import FailureInjectionReporter
from benchmarks.failure_injection.runner import (
    run_benchmark,
    select_cases,
)

pytestmark = pytest.mark.anyio


class AlwaysFailVerifier:
    """Mock verifier that always reports steps as failed."""

    def verify(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> VerificationOutcome:
        return VerificationOutcome(
            verification=StepVerification(
                result="failed", method=["url"], confidence=1.0
            ),
            checks=[
                Check(
                    kind="url_matches",
                    expected="test",
                    passed=False,
                    detail="forced fail",
                )
            ],
        )


class AlwaysPassVerifier:
    """Mock verifier that always reports steps as verified."""

    def verify(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> VerificationOutcome:
        return VerificationOutcome(
            verification=StepVerification(
                result="verified", method=["url"], confidence=1.0
            ),
            checks=[
                Check(
                    kind="url_matches",
                    expected="test",
                    passed=True,
                    detail="forced pass",
                )
            ],
        )


class CrashingVerifier:
    """Mock verifier that throws an unhandled exception."""

    def verify(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> VerificationOutcome:
        raise RuntimeError("Verifier internal engine malfunction")


# --------------------------------------------------------------------------------------------------
# Test cases integrity
# --------------------------------------------------------------------------------------------------


def test_cases_suite_contains_all_four_failure_modes() -> None:
    types: set[FailureType] = {c.failure_type for c in ALL_CASES}
    assert types == {
        "wrong_page",
        "missing_element",
        "unexpected_dialog",
        "wrong_form_value",
    }


def test_each_category_has_both_injected_failures_and_controls() -> None:
    categories = [
        WRONG_PAGE_CASES,
        MISSING_ELEMENT_CASES,
        UNEXPECTED_DIALOG_CASES,
        WRONG_FORM_VALUE_CASES,
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


# --------------------------------------------------------------------------------------------------
# Evaluator tests with LayeredVerifier and RuleVerifier
# --------------------------------------------------------------------------------------------------


async def test_evaluator_with_layered_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=LayeredVerifier())
    report = await evaluator.evaluate_all(ALL_CASES)

    assert report.total_cases == len(ALL_CASES)
    assert report.errors == 0
    assert report.detection_accuracy == 1.0
    assert report.false_alarm_rate == 0.0

    assert report.true_positives == report.injected_failures
    assert report.false_negatives == 0
    assert report.true_negatives == report.clean_controls
    assert report.false_positives == 0

    for ft in (
        "wrong_page",
        "missing_element",
        "unexpected_dialog",
        "wrong_form_value",
    ):
        type_metric = report.by_type[ft]  # type: ignore[index]
        assert type_metric.recall == 1.0
        assert type_metric.false_alarm_rate == 0.0
        assert type_metric.true_positives == type_metric.injected_failures
        assert type_metric.false_negatives == 0


async def test_evaluator_with_rule_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=RuleVerifier())
    report = await evaluator.evaluate_all(ALL_CASES)

    assert report.total_cases == len(ALL_CASES)
    assert report.errors == 0
    assert report.detection_accuracy == 1.0
    assert report.false_alarm_rate == 0.0


# --------------------------------------------------------------------------------------------------
# Evaluator edge cases: false alarms, misses, exceptions
# --------------------------------------------------------------------------------------------------


async def test_evaluator_detects_false_alarms_with_always_fail_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=AlwaysFailVerifier())
    report = await evaluator.evaluate_all(ALL_CASES)

    # Everything was flagged as failed
    # Injected failures: correctly caught (TP)
    # Clean controls: falsely flagged as failed (FP) -> false alarms!
    assert report.true_positives == report.injected_failures
    assert report.false_negatives == 0
    assert report.detection_accuracy == 1.0

    assert report.false_positives == report.clean_controls
    assert report.true_negatives == 0
    assert report.false_alarm_rate == 1.0


async def test_evaluator_detects_missed_failures_with_always_pass_verifier() -> None:
    evaluator = FailureInjectionEvaluator(verifier=AlwaysPassVerifier())
    report = await evaluator.evaluate_all(ALL_CASES)

    # Everything was flagged as verified
    # Injected failures: missed (FN)
    # Clean controls: correctly passed (TN)
    assert report.true_positives == 0
    assert report.false_negatives == report.injected_failures
    assert report.detection_accuracy == 0.0

    assert report.false_positives == 0
    assert report.true_negatives == report.clean_controls
    assert report.false_alarm_rate == 0.0


async def test_evaluator_handles_exceptions_gracefully() -> None:
    evaluator = FailureInjectionEvaluator(verifier=CrashingVerifier())
    report = await evaluator.evaluate_all(ALL_CASES[:2])

    assert report.total_cases == 2
    assert report.errors == 2
    for c in report.cases:
        assert c.classification == "ERROR"
        assert c.outcome_result == "error"
        assert c.error_message is not None
        assert "Verifier internal engine malfunction" in c.error_message


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
