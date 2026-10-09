"""Data models for benchmark trials and aggregated reports."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunTrial(BaseModel):
    """Result and metrics of a single benchmark trial run."""

    model_config = ConfigDict(extra="ignore")

    run_index: int = Field(ge=1, description="1-based index of the trial run.")
    success: bool = Field(description="Whether the trial run succeeded.")
    duration_seconds: float = Field(
        ge=0.0, description="Total wall-clock duration of the trial in seconds."
    )
    steps_taken: int = Field(ge=0, description="Number of execution steps taken.")
    retries_count: int = Field(
        ge=0, description="Number of step/verification retries encountered."
    )
    llm_call_count: int = Field(
        ge=0, description="Total number of LLM API requests made during the trial."
    )
    error_message: str | None = Field(
        default=None, description="Error message if the trial failed."
    )
    tokens_in: int = Field(
        default=0, ge=0, description="Input tokens used in LLM requests."
    )
    tokens_out: int = Field(
        default=0, ge=0, description="Output tokens used in LLM requests."
    )


class BenchmarkReport(BaseModel):
    """Aggregated benchmark report across multiple trials for a task."""

    model_config = ConfigDict(extra="ignore")

    task_name: str = Field(description="Name or description of the task benchmarked.")
    total_runs: int = Field(ge=0, description="Total number of trials executed.")
    successful_runs: int = Field(ge=0, description="Number of successful trials.")
    success_rate: float = Field(
        ge=0.0, le=1.0, description="Proportion of successful trials (0.0 to 1.0)."
    )
    average_duration_seconds: float = Field(
        ge=0.0, description="Mean duration per trial in seconds."
    )
    average_steps: float = Field(ge=0.0, description="Mean steps taken per trial.")
    total_llm_calls: int = Field(
        ge=0, description="Sum of all LLM calls across trials."
    )
    trials: list[RunTrial] = Field(
        default_factory=list, description="List of individual trial results."
    )

    min_steps: int = Field(
        default=0, ge=0, description="Minimum steps taken in any trial."
    )
    max_steps: int = Field(
        default=0, ge=0, description="Maximum steps taken in any trial."
    )
    total_retries: int = Field(
        default=0, ge=0, description="Total retries across all trials."
    )
    total_duration_seconds: float = Field(
        default=0.0, ge=0.0, description="Sum of wall-clock duration across all trials."
    )
    total_tokens_in: int = Field(
        default=0, ge=0, description="Total prompt tokens across all trials."
    )
    total_tokens_out: int = Field(
        default=0, ge=0, description="Total completion tokens across all trials."
    )
    timestamp: str = Field(
        default="", description="ISO timestamp when benchmark completed."
    )
