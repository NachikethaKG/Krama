"""Data models for benchmark reliability and performance reporting."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskMetrics(BaseModel):
    """Aggregated reliability, verification, and latency metrics for a benchmark task."""

    model_config = ConfigDict(extra="ignore")

    task_name: str = Field(description="Name or identifier of the benchmark task.")
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
    avg_latency_ms: float = Field(
        ge=0.0, description="Mean latency duration in milliseconds."
    )
    p90_latency_ms: float = Field(
        ge=0.0, description="90th percentile (P90) latency in milliseconds."
    )

    # Optional / defaulted fields to provide full breakdown
    failed_runs: int = Field(
        default=0, ge=0, description="Number of failed trial runs."
    )
    median_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Median (P50) latency in milliseconds."
    )
    total_runtime_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Sum of wall-clock duration across all trials in ms.",
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
        if self.failed_runs == 0 and self.total_runs > self.successful_runs:
            self.failed_runs = self.total_runs - self.successful_runs
        if self.median_latency_ms == 0.0 and self.avg_latency_ms > 0.0:
            self.median_latency_ms = self.avg_latency_ms
        if self.total_runtime_ms == 0.0 and self.avg_latency_ms > 0.0:
            self.total_runtime_ms = self.avg_latency_ms * self.total_runs
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
    overall_avg_latency_ms: float = Field(
        default=0.0, ge=0.0, description="Overall mean latency across all runs in ms."
    )
    overall_median_latency_ms: float = Field(
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
        if self.tasks and self.overall_total_runs == 0:
            self.overall_total_runs = sum(t.total_runs for t in self.tasks)
            self.overall_successful_runs = sum(t.successful_runs for t in self.tasks)
            self.overall_failed_runs = sum(t.failed_runs for t in self.tasks)
            self.overall_total_runtime_ms = sum(t.total_runtime_ms for t in self.tasks)
        return self

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
