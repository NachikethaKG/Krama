"""Evaluator for executing failure-injection cases and computing verifier accuracy metrics."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.contracts_gen.common_schema import (
    ExpectedState,
)
from app.verifier.layered import (
    LayeredVerifier,
    StepEvidence,
)

from benchmarks.failure_injection.cases import ALL_CASES
from benchmarks.failure_injection.models import (
    AccuracyReport,
    CaseResult,
    Classification,
    FailureCase,
    FailureType,
    TypeMetrics,
)

FAILURE_TYPES: tuple[FailureType, ...] = (
    "wrong_page",
    "missing_element",
    "unexpected_dialog",
    "wrong_form_value",
)


class FailureInjectionEvaluator:
    """Evaluates verifiers against synthetic and injected UI failure modes."""

    def __init__(self, verifier: Any | None = None) -> None:
        self.verifier = verifier if verifier is not None else LayeredVerifier()

    async def _call_verifier(
        self, expected: ExpectedState, evidence: StepEvidence
    ) -> Any:
        from app.verifier.verifier import RuleVerifier

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
        try:
            outcome = await self._call_verifier(case.expected, case.evidence)

            outcome_result: str = str(outcome.verification.result)
            confidence: float = float(outcome.verification.confidence)

            # Details on failed checks
            failures = outcome.failures() if hasattr(outcome, "failures") else []
            failed_checks = [
                f"{getattr(c, 'kind', 'check')}: {getattr(c, 'detail', '')}"
                for c in failures
            ]

            detected_as_failure = outcome_result == "failed"

            classification: Classification
            if case.is_failure:
                # We expected failure. If flagged failed -> TP, otherwise FN (missed)
                classification = "TP" if detected_as_failure else "FN"
            else:
                # We expected clean pass. If flagged failed -> FP (false alarm), otherwise TN
                classification = "FP" if detected_as_failure else "TN"

            return CaseResult(
                case_name=case.name,
                failure_type=case.failure_type,
                is_failure=case.is_failure,
                detected_as_failure=detected_as_failure,
                outcome_result=outcome_result,
                confidence=round(confidence, 2),
                classification=classification,
                failed_checks=failed_checks,
            )
        except Exception as exc:  # noqa: BLE001
            return CaseResult(
                case_name=case.name,
                failure_type=case.failure_type,
                is_failure=case.is_failure,
                detected_as_failure=False,
                outcome_result="error",
                confidence=0.0,
                classification="ERROR",
                error_message=f"{type(exc).__name__}: {exc}",
                failed_checks=[],
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
        """Compute aggregated metrics (recall, false alarm rate) across all evaluated cases."""
        ts = (timestamp or datetime.now(UTC)).isoformat()

        tp = sum(1 for r in results if r.classification == "TP")
        fn = sum(1 for r in results if r.classification == "FN")
        tn = sum(1 for r in results if r.classification == "TN")
        fp = sum(1 for r in results if r.classification == "FP")
        errors = sum(1 for r in results if r.classification == "ERROR")

        injected = tp + fn
        controls = tn + fp
        overall_recall = (tp / injected) if injected > 0 else 1.0
        overall_false_alarm = (fp / controls) if controls > 0 else 0.0

        by_type: dict[FailureType, TypeMetrics] = {}
        for ft in FAILURE_TYPES:
            type_results = [r for r in results if r.failure_type == ft]
            t_tp = sum(1 for r in type_results if r.classification == "TP")
            t_fn = sum(1 for r in type_results if r.classification == "FN")
            t_tn = sum(1 for r in type_results if r.classification == "TN")
            t_fp = sum(1 for r in type_results if r.classification == "FP")
            t_err = sum(1 for r in type_results if r.classification == "ERROR")

            t_inj = t_tp + t_fn
            t_ctrl = t_tn + t_fp
            t_recall = (t_tp / t_inj) if t_inj > 0 else 1.0
            t_far = (t_fp / t_ctrl) if t_ctrl > 0 else 0.0

            by_type[ft] = TypeMetrics(
                failure_type=ft,
                total_cases=len(type_results),
                injected_failures=t_inj,
                clean_controls=t_ctrl,
                true_positives=t_tp,
                false_negatives=t_fn,
                true_negatives=t_tn,
                false_positives=t_fp,
                errors=t_err,
                recall=round(t_recall, 4),
                false_alarm_rate=round(t_far, 4),
            )

        verifier_name = type(self.verifier).__name__

        return AccuracyReport(
            timestamp=ts,
            verifier_name=verifier_name,
            total_cases=len(results),
            injected_failures=injected,
            clean_controls=controls,
            true_positives=tp,
            false_negatives=fn,
            true_negatives=tn,
            false_positives=fp,
            errors=errors,
            detection_accuracy=round(overall_recall, 4),
            false_alarm_rate=round(overall_false_alarm, 4),
            by_type=by_type,
            cases=list(results),
        )

    def run(self, cases: Sequence[FailureCase] | None = None) -> AccuracyReport:
        """Synchronous convenience method to run the benchmark suite."""
        target_cases = cases if cases is not None else ALL_CASES
        return asyncio.run(self.evaluate_all(target_cases))
