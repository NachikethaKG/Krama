"""Data models for benchmark reliability and performance reporting."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskMetrics(BaseModel):
    """Aggregated reliability, verification, and latency metrics for a benchmark task."""

    model_config = ConfigDict(extra="ignore")

    task_name: str = Field(description="Name or identifier of the benchmark task.")
    platform: str = Field(
        default="gitea", description="Target platform: 'gitea' or 'github'."
    )
    total_runs: int = Field(ge=0, description="Total number of trial runs executed.")
    successful_runs: int = Field(ge=0, description="Number of successful trial runs.")
    success_rate: float = Field(
        ge=0.0, le=1.0, description="Success rate ratio between 0.0 and 1.0."
    )
    verifier_accuracy: float = Field(
        ge=0.0, le=1.0, description="Verifier detection accuracy ratio (0.0 to 1.0)."
    )
    false_alarm_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="False alarm / false positive rate ratio (0.0 to 1.0).",
    )
    replan_attempts: int = Field(
        default=0, ge=0, description="Total replan / recovery attempts."
    )
    replan_successes: int = Field(
        default=0, ge=0, description="Total successful recoveries after replanning."
    )
    recovery_rate: float = Field(
        default=0.0, ge=0.0, description="Recovery success percentage (0.0 to 100.0)."
    )
    avg_planning_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Average step planning latency in milliseconds.",
    )
    avg_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Mean latency duration in milliseconds."
    )
    p50_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="50th percentile / median latency in milliseconds.",
    )
    p90_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="90th percentile (P90) latency in milliseconds.",
    )
    total_runtime_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Sum of wall-clock duration across all trials in ms.",
    )

    # Optional / defaulted fields to provide full breakdown and backwards compatibility
    failed_runs: int = Field(
        default=0, ge=0, description="Number of failed trial runs."
    )
    median_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Median (P50) latency in milliseconds."
    )
    true_positive_detections: int = Field(
        default=0, ge=0, description="Count of true positive detections by verifier."
    )
    false_alarms_count: int = Field(
        default=0,
        ge=0,
        description="Count of false alarm / false positive verifier triggers.",
    )

    @model_validator(mode="after")
    def _compute_defaults(self) -> TaskMetrics:
        if not self.platform:
            self.platform = "github" if "github" in self.task_name.lower() else "gitea"
        if self.failed_runs == 0 and self.total_runs > self.successful_runs:
            self.failed_runs = self.total_runs - self.successful_runs
        if self.p50_latency_ms == 0.0 and self.median_latency_ms > 0.0:
            self.p50_latency_ms = self.median_latency_ms
        elif self.median_latency_ms == 0.0 and self.p50_latency_ms > 0.0:
            self.median_latency_ms = self.p50_latency_ms
        elif self.p50_latency_ms == 0.0 and self.avg_latency_ms > 0.0:
            self.p50_latency_ms = self.avg_latency_ms
            self.median_latency_ms = self.avg_latency_ms
        if self.total_runtime_ms == 0.0 and self.avg_latency_ms > 0.0:
            self.total_runtime_ms = self.avg_latency_ms * self.total_runs
        if self.recovery_rate == 0.0 and self.replan_attempts > 0:
            self.recovery_rate = round(
                (self.replan_successes / self.replan_attempts) * 100.0, 2
            )
        elif self.recovery_rate == 0.0 and self.replan_attempts == 0:
            self.recovery_rate = 100.0
        return self

    @property
    def avg_latency_s(self) -> float:
        """Average latency formatted in seconds."""
        return self.avg_latency_ms / 1000.0

    @property
    def p90_latency_s(self) -> float:
        """P90 latency formatted in seconds."""
        return self.p90_latency_ms / 1000.0

    @property
    def median_latency_s(self) -> float:
        """Median (P50) latency formatted in seconds."""
        return self.median_latency_ms / 1000.0

    @property
    def total_runtime_s(self) -> float:
        """Total runtime formatted in seconds."""
        return self.total_runtime_ms / 1000.0


class BenchmarkReportData(BaseModel):
    """Complete aggregated benchmark report data across all evaluated tasks."""

    model_config = ConfigDict(extra="ignore")

    generated_at: str = Field(
        description="ISO 8601 timestamp when report was generated."
    )
    total_tasks: int = Field(ge=0, description="Number of unique benchmark tasks.")
    overall_success_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall proportion of successful runs across all tasks.",
    )
    overall_verifier_accuracy: float = Field(
        ge=0.0, le=1.0, description="Overall verifier accuracy across all tasks."
    )
    tasks: list[TaskMetrics] = Field(
        default_factory=list,
        description="Per-task performance and reliability metrics.",
    )

    # Aggregated breakdown totals
    overall_total_runs: int = Field(
        default=0, ge=0, description="Sum of total runs across all tasks."
    )
    overall_successful_runs: int = Field(
        default=0, ge=0, description="Sum of successful runs across all tasks."
    )
    overall_failed_runs: int = Field(
        default=0, ge=0, description="Sum of failed runs across all tasks."
    )
    overall_false_alarm_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall false alarm rate across all tasks.",
    )
    overall_recovery_rate: float = Field(
        default=0.0,
        ge=0.0,
        description="Overall recovery rate percentage (0.0 to 100.0).",
    )
    overall_replan_attempts: int = Field(
        default=0, ge=0, description="Overall replan attempts across tasks."
    )
    overall_replan_successes: int = Field(
        default=0, ge=0, description="Overall replan successes across tasks."
    )
    overall_avg_planning_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Overall mean planning latency in ms."
    )
    overall_avg_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Overall mean latency across all runs in ms."
    )
    overall_median_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Overall median (P50) latency across all runs in ms.",
    )
    overall_p50_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Overall median (P50) latency across all runs in ms.",
    )
    overall_p90_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Overall 90th percentile latency across all runs in ms.",
    )
    overall_total_runtime_ms: float = Field(
        default=0.0, ge=0.0, description="Total wall-clock duration of all runs in ms."
    )

    @model_validator(mode="after")
    def _compute_overall_metrics(self) -> BenchmarkReportData:
        if self.tasks:
            if self.overall_total_runs == 0:
                self.overall_total_runs = sum(t.total_runs for t in self.tasks)
                self.overall_successful_runs = sum(t.successful_runs for t in self.tasks)
                self.overall_failed_runs = sum(t.failed_runs for t in self.tasks)
                self.overall_total_runtime_ms = sum(t.total_runtime_ms for t in self.tasks)
            if self.overall_replan_attempts == 0:
                self.overall_replan_attempts = sum(t.replan_attempts for t in self.tasks)
                self.overall_replan_successes = sum(t.replan_successes for t in self.tasks)
            if self.overall_recovery_rate == 0.0:
                if self.overall_replan_attempts > 0:
                    self.overall_recovery_rate = round(
                        (self.overall_replan_successes / self.overall_replan_attempts)
                        * 100.0,
                        2,
                    )
                else:
                    self.overall_recovery_rate = round(
                        sum(t.recovery_rate for t in self.tasks) / len(self.tasks), 2
                    )
            if self.overall_p50_latency_ms == 0.0:
                self.overall_p50_latency_ms = self.overall_median_latency_ms
            elif self.overall_median_latency_ms == 0.0:
                self.overall_median_latency_ms = self.overall_p50_latency_ms
        return self

    def to_contract_dict(self) -> dict[str, Any]:
        """Convert to dictionary matching the strict contracts/schemas/metrics-summary.schema.json schema."""
        return {
            "generated_at": self.generated_at,
            "total_tasks": self.total_tasks,
            "overall_success_rate": self.overall_success_rate,
            "overall_verifier_accuracy": self.overall_verifier_accuracy,
            "tasks": [
                {
                    "task_name": t.task_name,
                    "total_runs": t.total_runs,
                    "successful_runs": t.successful_runs,
                    "success_rate": t.success_rate,
                    "verifier_accuracy": t.verifier_accuracy,
                    "false_alarm_rate": t.false_alarm_rate,
                    "avg_latency_ms": t.avg_latency_ms,
                    "p90_latency_ms": t.p90_latency_ms,
                    "failed_runs": t.failed_runs,
                    "median_latency_ms": t.median_latency_ms or t.p50_latency_ms,
                    "total_runtime_ms": t.total_runtime_ms,
                    "true_positive_detections": t.true_positive_detections,
                    "false_alarms_count": t.false_alarms_count,
                }
                for t in self.tasks
            ],
            "overall_total_runs": self.overall_total_runs,
            "overall_successful_runs": self.overall_successful_runs,
            "overall_failed_runs": self.overall_failed_runs,
            "overall_false_alarm_rate": self.overall_false_alarm_rate,
            "overall_avg_latency_ms": self.overall_avg_latency_ms,
            "overall_median_latency_ms": self.overall_median_latency_ms
            or self.overall_p50_latency_ms,
            "overall_p90_latency_ms": self.overall_p90_latency_ms,
            "overall_total_runtime_ms": self.overall_total_runtime_ms,
        }

    @property
    def overall_avg_latency_s(self) -> float:
        return self.overall_avg_latency_ms / 1000.0

    @property
    def overall_p90_latency_s(self) -> float:
        return self.overall_p90_latency_ms / 1000.0

    @property
    def overall_median_latency_s(self) -> float:
        return self.overall_median_latency_ms / 1000.0

    @property
    def overall_total_runtime_s(self) -> float:
        return self.overall_total_runtime_ms / 1000.0
