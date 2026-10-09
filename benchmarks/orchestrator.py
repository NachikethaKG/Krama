"""Benchmark orchestrator running N iterations of agent execution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from benchmarks.agent_runner import AgentRunner
from benchmarks.collector import MetricsCollector
from benchmarks.gitea import GiteaResetError, GiteaTimeoutError, reset_gitea
from benchmarks.models import BenchmarkReport, RunTrial
from benchmarks.reporter import ConsoleReporter


class BenchmarkOrchestrator:
    """Coordinates benchmark trial loops, environment resets, and report generation."""

    def __init__(
        self,
        task: str,
        runs: int = 1,
        runner: AgentRunner | None = None,
        reset_fn: Callable[[], None] | None = None,
        collector: MetricsCollector | None = None,
        reporter: ConsoleReporter | None = None,
        results_dir: Path | None = None,
        skip_reset: bool = False,
    ) -> None:
        if runs < 1:
            raise ValueError(f"Runs must be >= 1, got {runs}")
        self.task = task
        self.runs = runs
        self.runner = runner or AgentRunner()
        self.reset_fn = reset_fn or (lambda: None if skip_reset else reset_gitea())
        self.collector = collector or MetricsCollector(task_name=task)
        self.reporter = reporter or ConsoleReporter()
        self.results_dir = results_dir
        self.skip_reset = skip_reset

    def run(self) -> tuple[BenchmarkReport, Path]:
        """Execute the N benchmark iterations and return (report, saved_path)."""
        for i in range(1, self.runs + 1):
            # 1. Reset Gitea before each run
            if not self.skip_reset:
                try:
                    self.reset_fn()
                except (GiteaTimeoutError, GiteaResetError) as exc:
                    # Record environment reset failure as a failed trial
                    failed_trial = RunTrial(
                        run_index=i,
                        success=False,
                        duration_seconds=0.0,
                        steps_taken=0,
                        retries_count=0,
                        llm_call_count=0,
                        error_message=f"Environment reset failed: {exc}",
                    )
                    self.collector.record_trial(failed_trial)
                    continue

            # 2. Invoke the agent via the runner
            trial = self.runner.run(run_index=i, task=self.task)
            self.collector.record_trial(trial)

        # 3. Aggregate metrics, save report and render summary
        report = self.collector.aggregate()
        saved_path = self.collector.save_report(report, results_dir=self.results_dir)
        self.reporter.render(report, saved_path=saved_path)
        return report, saved_path
