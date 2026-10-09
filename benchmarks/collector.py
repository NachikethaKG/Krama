"""Metrics collector and persistence for benchmark runs."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.models import BenchmarkReport, RunTrial


class MetricsCollector:
    """Collects individual run trials and aggregates them into a BenchmarkReport."""

    def __init__(self, task_name: str) -> None:
        self.task_name = task_name
        self.trials: list[RunTrial] = []

    def record_trial(self, trial: RunTrial) -> None:
        """Add a completed trial to the collector."""
        self.trials.append(trial)

    def aggregate(self, timestamp: datetime | None = None) -> BenchmarkReport:
        """Compute aggregated statistics across all recorded trials."""
        ts = timestamp or datetime.now(UTC)
        total_runs = len(self.trials)
        successful_runs = sum(1 for t in self.trials if t.success)
        success_rate = (successful_runs / total_runs) if total_runs > 0 else 0.0
        avg_duration = (
            sum(t.duration_seconds for t in self.trials) / total_runs
            if total_runs > 0
            else 0.0
        )
        avg_steps = (
            (sum(t.steps_taken for t in self.trials) / total_runs)
            if total_runs > 0
            else 0.0
        )
        min_steps = min((t.steps_taken for t in self.trials), default=0)
        max_steps = max((t.steps_taken for t in self.trials), default=0)
        total_llm = sum(t.llm_call_count for t in self.trials)
        total_retries = sum(t.retries_count for t in self.trials)
        total_tokens_in = sum(t.tokens_in for t in self.trials)
        total_tokens_out = sum(t.tokens_out for t in self.trials)
        total_duration = sum(t.duration_seconds for t in self.trials)

        return BenchmarkReport(
            task_name=self.task_name,
            total_runs=total_runs,
            successful_runs=successful_runs,
            success_rate=round(success_rate, 4),
            average_duration_seconds=round(avg_duration, 3),
            average_steps=round(avg_steps, 2),
            total_llm_calls=total_llm,
            trials=list(self.trials),
            min_steps=min_steps,
            max_steps=max_steps,
            total_retries=total_retries,
            total_duration_seconds=round(total_duration, 3),
            total_tokens_in=total_tokens_in,
            total_tokens_out=total_tokens_out,
            timestamp=ts.isoformat(),
        )

    def save_report(
        self,
        report: BenchmarkReport,
        results_dir: Path | None = None,
        timestamp: datetime | None = None,
    ) -> Path:
        """Persist benchmark report to `benchmarks/results/<task>-<timestamp>.json`."""
        ts = timestamp or datetime.now(UTC)
        target_dir = results_dir or (Path(__file__).resolve().parent / "results")
        target_dir.mkdir(parents=True, exist_ok=True)

        task_slug = re.sub(r"[^\w\-]+", "_", self.task_name).strip("_").lower()
        if not task_slug:
            task_slug = "benchmark"
        formatted_ts = ts.strftime("%Y%m%d_%H%M%S")
        filename = f"{task_slug}_{formatted_ts}.json"
        output_path = target_dir / filename

        output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return output_path
