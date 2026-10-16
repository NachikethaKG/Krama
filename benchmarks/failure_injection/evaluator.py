"""Evaluator for executing failure-injection cases and computing verifier accuracy metrics.

Scoring rules (table in `benchmarks.failure_injection.models`):
- a verifier crash is never free: on an injected case it is a miss (FN), on a control a false alarm (FP);
- `skipped` is its own outcome: on an injected case it is "caught for a human" (the run pauses), on a
  control it is a needless pause;
- `verified` on an injected case is the dangerous one: the run silently continues on a broken step;
- every rate is 0 when there is nothing to count (no free 100%).
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from app.contracts_gen.common_schema import (
    ExpectedState,
)
from app.verifier.layered import (
    LayeredVerifier,
    StepEvidence,
)
from app.verifier.verifier import RuleVerifier

from benchmarks.failure_injection.cases import ALL_CASES
from benchmarks.failure_injection.models import (
    AccuracyReport,
    CaseResult,
    Classification,
    FailureCase,
    FailureType,
    Outcome,
    OutcomeCounts,
    TypeMetrics,
)

FAILURE_TYPES: tuple[FailureType, ...] = (
    "wrong_page",
    "missing_element",
    "unexpected_dialog",
    "wrong_form_value",
    "weak_signal",
)


def classify(is_failure: bool, outcome: Outcome) -> Classification:
    """Confusion-matrix label for one verifier outcome."""
    if is_failure:
        if outcome == "failed":
            return "TP"
        if outcome == "skipped":
            return "TP_PAUSED"
        return "FN"  # verified (silently passed) or crashed
    if outcome == "verified":
        return "TN"
    if outcome == "skipped":
        return "FP_PAUSED"
    return "FP"  # failed or crashed


def _to_outcome(raw: str) -> Outcome:
    if raw in ("verified", "failed", "skipped"):
        return cast(Outcome, raw)
    raise ValueError(f"verifier returned unknown result {raw!r}")


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator > 0 else 0.0


def _outcomes(results: Sequence[CaseResult]) -> OutcomeCounts:
    def n(outcome: Outcome) -> int:
        return sum(1 for r in results if r.outcome_result == outcome)

    return OutcomeCounts(
        verified=n("verified"),
        failed=n("failed"),
        skipped=n("skipped"),
        error=n("error"),
    )


def _type_metrics(ft: FailureType, results: Sequence[CaseResult]) -> TypeMetrics:
    def count(label: Classification) -> int:
        return sum(1 for r in results if r.classification == label)

    injected = [r for r in results if r.is_failure]
    controls = [r for r in results if not r.is_failure]
    inj_out, ctrl_out = _outcomes(injected), _outcomes(controls)
    tp, paused = count("TP"), count("TP_PAUSED")
    return TypeMetrics(
        failure_type=ft,
        total_cases=len(results),
        injected_failures=len(injected),
        clean_controls=len(controls),
        true_positives=tp,
        paused_failures=paused,
        false_negatives=count("FN"),
        true_negatives=count("TN"),
        false_positives=count("FP"),
        needless_pauses=count("FP_PAUSED"),
        errors=inj_out.error + ctrl_out.error,
        injected_outcomes=inj_out,
        control_outcomes=ctrl_out,
        recall=_rate(tp + paused, len(injected)),
        hard_detection_rate=_rate(tp, len(injected)),
        silently_passed_rate=_rate(inj_out.verified, len(injected)),
        false_alarm_rate=_rate(count("FP"), len(controls)),
        needless_pause_rate=_rate(count("FP_PAUSED"), len(controls)),
    )


class FailureInjectionEvaluator:
    """Evaluates verifiers against synthetic and injected UI failure modes."""

    def __init__(self, verifier: Any | None = None) -> None:
        self.verifier = verifier if verifier is not None else LayeredVerifier()

    async def _call_verifier(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> Any:
        v: Any = self.verifier
        if isinstance(v, RuleVerifier):
            res = v.verify(expected, evidence.after)
        elif isinstance(v, LayeredVerifier):
            res = await v.verify(expected, evidence)
        else:
            try:
                res = v.verify(expected, evidence)
            except (TypeError, AttributeError):
                res = v.verify(expected, evidence.after)

        if inspect.isawaitable(res):
            return await res
        return res

    async def evaluate_case(self, case: FailureCase) -> CaseResult:
        """Run a single failure case through the verifier and classify the outcome."""
        outcome_result: Outcome
        error_message: str | None = None
        failed_checks: list[str] = []
        try:
            outcome = await self._call_verifier(case.expected, case.evidence)
            outcome_result = _to_outcome(str(outcome.verification.result))
            confidence = float(outcome.verification.confidence)
            failures = outcome.failures() if hasattr(outcome, "failures") else []
            failed_checks = [
                f"{getattr(c, 'kind', 'check')}: {getattr(c, 'detail', '')}"
                for c in failures
            ]
        except Exception as exc:  # noqa: BLE001 - a crash is scored, never raised
            outcome_result = "error"
            confidence = 0.0
            error_message = f"{type(exc).__name__}: {exc}"

        return CaseResult(
            case_name=case.name,
            failure_type=case.failure_type,
            is_failure=case.is_failure,
            detected_as_failure=outcome_result == "failed",
            outcome_result=outcome_result,
            expected_result=case.expected_result,
            matches_expected=outcome_result == case.expected_result,
            confidence=round(confidence, 2),
            classification=classify(case.is_failure, outcome_result),
            error_message=error_message,
            failed_checks=failed_checks,
        )

    async def evaluate_all(self, cases: Sequence[FailureCase]) -> AccuracyReport:
        """Evaluate all specified cases and aggregate detection and false alarm metrics."""
        results: list[CaseResult] = []
        for case in cases:
            res = await self.evaluate_case(case)
            results.append(res)

        return self.aggregate(results)

    def aggregate(
        self,
        results: Sequence[CaseResult],
        timestamp: datetime | None = None,
    ) -> AccuracyReport:
        """Compute aggregated metrics across all evaluated cases."""
        ts = (timestamp or datetime.now(UTC)).isoformat()
        by_type: dict[FailureType, TypeMetrics] = {
            ft: _type_metrics(ft, [r for r in results if r.failure_type == ft])
            for ft in FAILURE_TYPES
        }
        o = _type_metrics("weak_signal", results)  # all cases; the label is unused

        return AccuracyReport(
            timestamp=ts,
            verifier_name=type(self.verifier).__name__,
            total_cases=o.total_cases,
            injected_failures=o.injected_failures,
            clean_controls=o.clean_controls,
            true_positives=o.true_positives,
            paused_failures=o.paused_failures,
            false_negatives=o.false_negatives,
            silently_passed=o.injected_outcomes.verified,
            true_negatives=o.true_negatives,
            false_positives=o.false_positives,
            needless_pauses=o.needless_pauses,
            errors=o.errors,
            expected_mismatches=sum(1 for r in results if r.matches_expected is False),
            detection_accuracy=o.recall,
            hard_detection_rate=o.hard_detection_rate,
            silently_passed_rate=o.silently_passed_rate,
            false_alarm_rate=o.false_alarm_rate,
            needless_pause_rate=o.needless_pause_rate,
            by_type=by_type,
            cases=list(results),
        )

    def run(self, cases: Sequence[FailureCase] | None = None) -> AccuracyReport:
        """Synchronous convenience method to run the benchmark suite."""
        target_cases = cases if cases is not None else ALL_CASES
        return asyncio.run(self.evaluate_all(target_cases))
