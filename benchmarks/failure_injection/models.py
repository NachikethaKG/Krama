"""Data models for failure-injection verification benchmark and accuracy reporting."""

from __future__ import annotations

from typing import Literal

from app.contracts_gen.common_schema import (
    ExpectedState,
)
from app.verifier.layered import StepEvidence
from pydantic import BaseModel, ConfigDict, Field

FailureType = Literal[
    "wrong_page", "missing_element", "unexpected_dialog", "wrong_form_value"
]
Classification = Literal["TP", "FN", "TN", "FP", "ERROR"]


class FailureCase(BaseModel):
    """Specification of a single benchmark case (either injected failure or clean control)."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str = Field(description="Unique identifier for the benchmark case.")
    failure_type: FailureType = Field(description="Category of UI failure mode tested.")
    description: str = Field(description="Explanation of what this case tests.")
    is_failure: bool = Field(
        description="True if an injected fault (should fail), False if a clean control step (should pass)."
    )
    expected: ExpectedState = Field(
        description="ExpectedState condition given to the verifier."
    )
    evidence: StepEvidence = Field(
        description="StepEvidence (action, target, before/after states) tested."
    )


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
    outcome_result: str = Field(
        description="Verifier outcome result string ('failed', 'verified', 'skipped', 'error')."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score reported by the verifier."
    )
    classification: Classification = Field(
        description="Confusion matrix outcome: TP (caught failure), FN (missed failure), "
        "TN (correct control pass), FP (false alarm on clean control), ERROR (runtime exception)."
    )
    error_message: str | None = Field(
        default=None,
        description="Exception message if an error occurred during verification.",
    )
    failed_checks: list[str] = Field(
        default_factory=list, description="Summary details of checks that failed."
    )


class TypeMetrics(BaseModel):
    """Metrics aggregated for a specific failure type category."""

    model_config = ConfigDict(extra="ignore")

    failure_type: FailureType = Field(description="Failure category name.")
    total_cases: int = Field(
        ge=0, description="Total number of cases evaluated in this category."
    )
    injected_failures: int = Field(
        ge=0, description="Total injected failure cases (TP + FN)."
    )
    clean_controls: int = Field(
        ge=0, description="Total clean control cases (TN + FP)."
    )
    true_positives: int = Field(
        ge=0, description="Injected failures correctly caught (TP)."
    )
    false_negatives: int = Field(
        ge=0, description="Injected failures missed by verifier (FN)."
    )
    true_negatives: int = Field(
        ge=0, description="Clean control steps correctly passed (TN)."
    )
    false_positives: int = Field(
        ge=0, description="Clean control steps falsely flagged as failed (FP)."
    )
    errors: int = Field(
        default=0, ge=0, description="Number of execution or runtime errors."
    )
    recall: float = Field(
        ge=0.0,
        le=1.0,
        description="Detection accuracy (recall): TP / (TP + FN).",
    )
    false_alarm_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="False alarm rate: FP / (FP + TN).",
    )


class AccuracyReport(BaseModel):
    """Overall benchmark report summarizing verifier detection accuracy and false alarms."""

    model_config = ConfigDict(extra="ignore")

    timestamp: str = Field(description="ISO timestamp when benchmark completed.")
    verifier_name: str = Field(description="Name or class of the verifier evaluated.")
    total_cases: int = Field(ge=0, description="Total number of cases evaluated.")
    injected_failures: int = Field(
        ge=0, description="Total injected failures across all categories."
    )
    clean_controls: int = Field(
        ge=0, description="Total clean controls across all categories."
    )
    true_positives: int = Field(
        ge=0, description="Total true positives (caught failures)."
    )
    false_negatives: int = Field(
        ge=0, description="Total false negatives (missed failures)."
    )
    true_negatives: int = Field(
        ge=0, description="Total true negatives (clean passes)."
    )
    false_positives: int = Field(
        ge=0, description="Total false positives (false alarms)."
    )
    errors: int = Field(default=0, ge=0, description="Total evaluation errors.")
    detection_accuracy: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall detection accuracy (recall): TP / (TP + FN).",
    )
    false_alarm_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall false alarm rate: FP / (FP + TN).",
    )
    by_type: dict[FailureType, TypeMetrics] = Field(
        description="Breakdown of metrics by failure category."
    )
    cases: list[CaseResult] = Field(
        default_factory=list, description="Detailed per-case results."
    )
