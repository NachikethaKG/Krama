"""Benchmark orchestrator running N iterations of agent execution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from benchmarks.agent_runner import AgentRunner
from benchmarks.collector import MetricsCollector
from benchmarks.gitea import GiteaResetError, GiteaTimeoutError, reset_gitea
from benchmarks.models import BenchmarkReport, RunTrial
from benchmarks.reporter import ConsoleReporter
from benchmarks.tasks.runner import TaskSetupError, check_success, run_setup
from benchmarks.tasks.schema import BenchmarkTask


class TrialRunner(Protocol):
    """Runs one trial of a task prompt: AgentRunner (the CLI loop) or ApiAgentRunner (the backend API)."""

    def run(self, run_index: int, task: str) -> RunTrial: ...


class BenchmarkOrchestrator:
    """Coordinates benchmark trial loops, environment resets, and report generation."""

    def __init__(
        self,
        task: str,
        runs: int = 1,
        runner: TrialRunner | None = None,
        reset_fn: Callable[[], None] | None = None,
        collector: MetricsCollector | None = None,
        reporter: ConsoleReporter | None = None,
        results_dir: Path | None = None,
        skip_reset: bool = False,
        spec: BenchmarkTask | None = None,
    ) -> None:
        """`spec`: a task file (benchmarks/tasks/*.yaml). Then each trial starts from the task's own setup and
        succeeds only if the task's success_check passes; the agent never grades itself."""
        if runs < 1:
            raise ValueError(f"Runs must be >= 1, got {runs}")
        self.spec = spec
        self.task = spec.prompt if spec is not None else task
        self.runs = runs
        self.runner: TrialRunner = runner or AgentRunner()
        if reset_fn is None and spec is not None:

            def reset_fn() -> None:
                run_setup(spec)
        self.reset_fn = reset_fn or (lambda: None if skip_reset else reset_gitea())
        self.collector = collector or MetricsCollector(task_name=spec.name if spec is not None else task)
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
                except (GiteaTimeoutError, GiteaResetError, TaskSetupError) as exc:
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
            if self.spec is not None:
                check = check_success(self.spec)
                trial = trial.model_copy(
                    update={
                        "agent_verified": trial.success,
                        "success": check.passed,
                        "independent_check": check.detail,
                    }
                )
            self.collector.record_trial(trial)

        # 3. Aggregate metrics, save report and render summary
        report = self.collector.aggregate()
        saved_path = self.collector.save_report(report, results_dir=self.results_dir)
        self.reporter.render(report, saved_path=saved_path)
        return report, saved_path
