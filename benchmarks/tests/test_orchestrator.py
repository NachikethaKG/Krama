from pathlib import Path
from unittest.mock import MagicMock

import pytest

from benchmarks.agent_runner import AgentRunner
from benchmarks.gitea import GiteaTimeoutError
from benchmarks.models import RunTrial
from benchmarks.orchestrator import BenchmarkOrchestrator


def test_orchestrator_happy_path(tmp_path: Path) -> None:
    reset_calls: list[int] = []

    def mock_reset() -> None:
        reset_calls.append(len(reset_calls) + 1)

    mock_runner = MagicMock(spec=AgentRunner)
    mock_runner.run.side_effect = [
        RunTrial(
            run_index=1,
            success=True,
            duration_seconds=2.0,
            steps_taken=4,
            retries_count=0,
            llm_call_count=1,
            tokens_in=100,
            tokens_out=20,
        ),
        RunTrial(
            run_index=2,
            success=True,
            duration_seconds=2.2,
            steps_taken=4,
            retries_count=0,
            llm_call_count=1,
            tokens_in=105,
            tokens_out=22,
        ),
    ]

    orchestrator = BenchmarkOrchestrator(
        task="Create demo repo",
        runs=2,
        runner=mock_runner,
        reset_fn=mock_reset,
        results_dir=tmp_path,
    )

    report, saved_path = orchestrator.run()

    assert len(reset_calls) == 2
    assert report.total_runs == 2
    assert report.successful_runs == 2
    assert report.success_rate == 1.0
    assert report.average_steps == 4.0
    assert report.total_llm_calls == 2
    assert saved_path.exists()


def test_orchestrator_handles_agent_crash_without_crashing_benchmark(tmp_path: Path) -> None:
    mock_runner = MagicMock(spec=AgentRunner)
    mock_runner.run.side_effect = [
        RunTrial(
            run_index=1,
            success=True,
            duration_seconds=3.0,
            steps_taken=4,
            retries_count=0,
            llm_call_count=1,
        ),
        RunTrial(
            run_index=2,
            success=False,
            duration_seconds=1.2,
            steps_taken=1,
            retries_count=1,
            llm_call_count=1,
            error_message="Process crashed: exit code 1",
        ),
    ]

    orchestrator = BenchmarkOrchestrator(
        task="Create demo repo",
        runs=2,
        runner=mock_runner,
        reset_fn=lambda: None,
        results_dir=tmp_path,
    )

    report, saved_path = orchestrator.run()

    # The benchmark must complete all runs rather than aborting on failure
    assert report.total_runs == 2
    assert report.successful_runs == 1
    assert report.success_rate == 0.5
    assert len(report.trials) == 2
    assert report.trials[0].success is True
    assert report.trials[1].success is False
    assert "Process crashed" in str(report.trials[1].error_message)
    assert saved_path.exists()


def test_orchestrator_handles_gitea_reset_timeout(tmp_path: Path) -> None:
    reset_count = 0

    def flaky_reset() -> None:
        nonlocal reset_count
        reset_count += 1
        if reset_count == 2:
            raise GiteaTimeoutError("Gitea reset timed out after 10s")

    mock_runner = MagicMock(spec=AgentRunner)
    mock_runner.run.return_value = RunTrial(
        run_index=1,
        success=True,
        duration_seconds=2.0,
        steps_taken=4,
        retries_count=0,
        llm_call_count=1,
    )

    orchestrator = BenchmarkOrchestrator(
        task="Create demo repo",
        runs=2,
        runner=mock_runner,
        reset_fn=flaky_reset,
        results_dir=tmp_path,
    )

    report, _saved_path = orchestrator.run()

    assert report.total_runs == 2
    assert report.successful_runs == 1
    assert report.success_rate == 0.5
    assert report.trials[1].success is False
    assert "Environment reset failed" in str(report.trials[1].error_message)


def test_orchestrator_validates_runs_count() -> None:
    with pytest.raises(ValueError, match="Runs must be >= 1"):
        BenchmarkOrchestrator(task="Test", runs=0)
