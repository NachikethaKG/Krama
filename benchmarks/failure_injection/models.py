"""Data models for failure-injection verification benchmark and accuracy reporting.

How a verifier result is scored (docs/research/phase-1-together-verified-definition.md):

| Case     | `failed`             | `skipped`                    | `verified`              | crash (`error`)   |
|----------|----------------------|------------------------------|-------------------------|-------------------|
| injected | TP (hard catch)      | TP_PAUSED (caught for human) | FN (silently passed!)   | FN (miss)         |
| control  | FP (false alarm)     | FP_PAUSED (needless pause)   | TN                      | FP (false alarm)  |

`skipped` pauses the run for a human, so on an injected failure it is NOT a miss; it is reported apart from
`failed`. The dangerous outcome is `verified` on an injected failure: the run continues on a broken step.
"""

from __future__ import annotations

from typing import Literal

from app.contracts_gen.common_schema import (
    ExpectedState,
)
from app.verifier.layered import StepEvidence
from pydantic import BaseModel, ConfigDict, Field, model_validator

FailureType = Literal[
    "wrong_page",
    "missing_element",
    "unexpected_dialog",
    "wrong_form_value",
    "weak_signal",
]
Outcome = Literal["verified", "failed", "skipped", "error"]
ExpectedResult = Literal["verified", "failed", "skipped"]
Classification = Literal["TP", "TP_PAUSED", "FN", "TN", "FP", "FP_PAUSED"]


class FailureCase(BaseModel):
    """Specification of a single benchmark case (either injected failure or clean control)."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str = Field(description="Unique identifier for the benchmark case.")
    failure_type: FailureType = Field(description="Category of UI failure mode tested.")
    description: str = Field(description="Explanation of what this case tests.")
    is_failure: bool = Field(
        description="True if an injected fault (must not verify), False if a clean control step."
    )
    expected_result: ExpectedResult = Field(
        description="The result a correct verifier gives (per the agreed 'verified' definition). "
        "'failed' when the evidence contradicts the expectation, 'skipped' when nothing contradicts "
        "it but nothing proves the step had an effect either (weak signals), 'verified' for controls."
    )
    expected: ExpectedState = Field(
        description="ExpectedState condition given to the verifier."
    )
    evidence: StepEvidence = Field(
        description="StepEvidence (action, target, before/after states) tested."
    )

    @model_validator(mode="after")
    def _expected_result_matches_kind(self) -> FailureCase:
        if self.is_failure and self.expected_result == "verified":
            raise ValueError(
                f"{self.name}: an injected failure can never expect 'verified'"
            )
        if not self.is_failure and self.expected_result != "verified":
            raise ValueError(f"{self.name}: a clean control must expect 'verified'")
        return self


class CaseResult(BaseModel):
    """Result of running a single failure case through a verifier."""

    model_config = ConfigDict(extra="ignore")

    case_name: str = Field(description="Identifier of the evaluated case.")
    failure_type: FailureType = Field(description="Failure mode tested.")
    is_failure: bool = Field(
        description="Whether the case had an intentional injected failure."
    )
    detected_as_failure: bool = Field(
        description="Whether the verifier reported the step as failed (result == 'failed')."
    )
    outcome_result: Outcome = Field(
        description="Verifier outcome ('failed', 'verified', 'skipped', or 'error' if it crashed)."
    )
    expected_result: ExpectedResult | None = Field(
        default=None, description="The result the case declares as correct."
    )
    matches_expected: bool | None = Field(
        default=None,
        description="Whether outcome_result equals expected_result (None if not declared).",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score reported by the verifier."
    )
    classification: Classification = Field(
        description="TP (injected, failed), TP_PAUSED (injected, skipped: caught for a human), "
        "FN (injected, verified or crashed), TN (control, verified), FP (control, failed or crashed), "
        "FP_PAUSED (control, skipped: needless pause)."
    )
    error_message: str | None = Field(
        default=None,
        description="Exception message if an error occurred during verification.",
    )
    failed_checks: list[str] = Field(
        default_factory=list, description="Summary details of checks that failed."
    )


class OutcomeCounts(BaseModel):
    """How many cases came back with each verifier result."""

    model_config = ConfigDict(extra="ignore")

    verified: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)


class TypeMetrics(BaseModel):
    """Metrics aggregated for a specific failure type category."""

    model_config = ConfigDict(extra="ignore")

    failure_type: FailureType = Field(description="Failure category name.")
    total_cases: int = Field(
        ge=0, description="Total number of cases evaluated in this category."
    )
    injected_failures: int = Field(
        ge=0,
        description="Injected failure cases (TP + TP_PAUSED + FN; errors included).",
    )
    clean_controls: int = Field(
        ge=0, description="Clean control cases (TN + FP + FP_PAUSED; errors included)."
    )
    true_positives: int = Field(
        ge=0, description="Injected failures the verifier reported as failed (TP)."
    )
    paused_failures: int = Field(
        default=0,
        ge=0,
        description="Injected failures the verifier reported as skipped (TP_PAUSED, caught for a human).",
    )
    false_negatives: int = Field(
        ge=0, description="Injected failures verified or crashed on (FN)."
    )
    true_negatives: int = Field(
        ge=0, description="Clean control steps correctly verified (TN)."
    )
    false_positives: int = Field(
        ge=0, description="Clean control steps reported failed or crashed on (FP)."
    )
    needless_pauses: int = Field(
        default=0,
        ge=0,
        description="Clean control steps reported skipped (FP_PAUSED, a soft false alarm).",
    )
    errors: int = Field(
        default=0, ge=0, description="Number of execution or runtime errors."
    )
    injected_outcomes: OutcomeCounts = Field(default_factory=OutcomeCounts)
    control_outcomes: OutcomeCounts = Field(default_factory=OutcomeCounts)
    recall: float = Field(
        ge=0.0,
        le=1.0,
        description="Not-silently-passed rate: (TP + TP_PAUSED) / injected (0 if no injected cases).",
    )
    hard_detection_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="TP / injected."
    )
    silently_passed_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Injected cases that came back 'verified' / injected. Must be 0.",
    )
    false_alarm_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Hard false alarm rate: FP / controls (0 if no controls).",
    )
    needless_pause_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="FP_PAUSED / controls."
    )


class AccuracyReport(BaseModel):
    """Overall benchmark report summarizing verifier detection accuracy and false alarms."""

    model_config = ConfigDict(extra="ignore")

    timestamp: str = Field(description="ISO timestamp when benchmark completed.")
    verifier_name: str = Field(description="Name or class of the verifier evaluated.")
    total_cases: int = Field(ge=0, description="Total number of cases evaluated.")
    injected_failures: int = Field(
        ge=0,
        description="Total injected failures across all categories (errors included).",
    )
    clean_controls: int = Field(
        ge=0,
        description="Total clean controls across all categories (errors included).",
    )
    true_positives: int = Field(
        ge=0, description="Injected failures reported as failed (TP)."
    )
    paused_failures: int = Field(
        default=0,
        ge=0,
        description="Injected failures reported as skipped (TP_PAUSED).",
    )
    false_negatives: int = Field(
        ge=0, description="Injected failures verified or crashed on (FN)."
    )
    silently_passed: int = Field(
        default=0,
        ge=0,
        description="Injected failures reported as verified. Must be 0.",
    )
    true_negatives: int = Field(ge=0, description="Clean controls verified (TN).")
    false_positives: int = Field(
        ge=0, description="Clean controls reported failed or crashed on (FP)."
    )
    needless_pauses: int = Field(
        default=0, ge=0, description="Clean controls reported skipped (FP_PAUSED)."
    )
    errors: int = Field(default=0, ge=0, description="Total evaluation errors.")
    expected_mismatches: int = Field(
        default=0,
        ge=0,
        description="Cases whose outcome differs from the case's declared expected_result.",
    )
    detection_accuracy: float = Field(
        ge=0.0,
        le=1.0,
        description="Not-silently-passed rate: (TP + TP_PAUSED) / injected (0 if no injected cases).",
    )
    hard_detection_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="TP / injected."
    )
    silently_passed_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="silently_passed / injected. Must be 0.",
    )
    false_alarm_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Hard false alarm rate: FP / controls (0 if no controls).",
    )
    needless_pause_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="FP_PAUSED / controls."
    )
    by_type: dict[FailureType, TypeMetrics] = Field(
        description="Breakdown of metrics by failure category."
    )
    cases: list[CaseResult] = Field(
        default_factory=list, description="Detailed per-case results."
    )
