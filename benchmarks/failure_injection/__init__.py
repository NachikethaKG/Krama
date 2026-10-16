"""Verifier failure-injection benchmark package for measuring detection accuracy and false alarms."""

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
    CaseResult,
    Classification,
    FailureCase,
    FailureType,
    Outcome,
    OutcomeCounts,
    TypeMetrics,
)
from benchmarks.failure_injection.reporter import FailureInjectionReporter

__all__ = [
    "ALL_CASES",
    "MISSING_ELEMENT_CASES",
    "UNEXPECTED_DIALOG_CASES",
    "WEAK_SIGNAL_CASES",
    "WRONG_FORM_VALUE_CASES",
    "WRONG_PAGE_CASES",
    "AccuracyReport",
    "CaseResult",
    "Classification",
    "FailureCase",
    "FailureInjectionEvaluator",
    "FailureInjectionReporter",
    "FailureType",
    "Outcome",
    "OutcomeCounts",
    "TypeMetrics",
]
