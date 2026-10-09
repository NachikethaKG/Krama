import io
from pathlib import Path
from unittest.mock import patch

import pytest

from benchmarks.models import BenchmarkReport, RunTrial
from benchmarks.reporter import ConsoleReporter
from benchmarks.runner import main, parse_args


def test_console_reporter_output() -> None:
    buf = io.StringIO()
    reporter = ConsoleReporter(stream=buf)

    report = BenchmarkReport(
        task_name="Create demo repository",
        total_runs=2,
        successful_runs=2,
        success_rate=1.0,
        average_duration_seconds=5.25,
        average_steps=4.0,
        total_llm_calls=4,
        min_steps=4,
        max_steps=4,
        total_retries=1,
        total_duration_seconds=10.5,
        total_tokens_in=500,
        total_tokens_out=120,
        trials=[
            RunTrial(
                run_index=1,
                success=True,
                duration_seconds=5.0,
                steps_taken=4,
                retries_count=0,
                llm_call_count=2,
            ),
            RunTrial(
                run_index=2,
                success=True,
                duration_seconds=5.5,
                steps_taken=4,
                retries_count=1,
                llm_call_count=2,
            ),
        ],
    )

    reporter.render(report, saved_path=Path("benchmarks/results/test.json"))
    out = buf.getvalue()

    assert "BENCHMARK SUMMARY REPORT" in out
    assert "Task:                    Create demo repository" in out
    assert "Success Rate:            100.0% (2/2)" in out
    assert "min: 4 | max: 4 | mean: 4.0" in out
    assert "Total Retries:           1" in out
    assert "LLM API Requests:        4 calls" in out
    assert "Run #1   [PASSED]" in out
    assert "Run #2   [PASSED]" in out
    assert "Report saved to: " in out
    assert "test.json" in out


def test_parse_args_variations() -> None:
    # 1. Flag arguments
    t, r, _ = parse_args(["--task", "Task A", "--runs", "5"])
    assert t == "Task A"
    assert r == 5

    # 2. Positional arguments
    t, r, _ = parse_args(["Task B", "3"])
    assert t == "Task B"
    assert r == 3

    # 3. Mixed positional and flag
    t, r, _ = parse_args(["Task C", "--runs", "4"])
    assert t == "Task C"
    assert r == 4

    # 4. Default runs = 1
    t, r, _ = parse_args(["--task", "Task D"])
    assert t == "Task D"
    assert r == 1

    # 5. Invalid / missing task
    with pytest.raises(SystemExit):
        parse_args([])

    # 6. Invalid runs count
    with pytest.raises(SystemExit):
        parse_args(["Task E", "--runs", "0"])


def test_runner_main_success_returns_zero(tmp_path: Path) -> None:
    mock_report = BenchmarkReport(
        task_name="Task Success",
        total_runs=1,
        successful_runs=1,
        success_rate=1.0,
        average_duration_seconds=1.0,
        average_steps=2.0,
        total_llm_calls=1,
        trials=[],
    )

    with (
        patch("benchmarks.runner.reset_gitea"),
        patch(
            "benchmarks.orchestrator.BenchmarkOrchestrator.run",
            return_value=(mock_report, tmp_path / "result.json"),
        ),
    ):
        code = main(
            ["--task", "Task Success", "--runs", "1", "--results-dir", str(tmp_path)]
        )
        assert code == 0


def test_runner_main_failure_returns_one(tmp_path: Path) -> None:
    mock_report = BenchmarkReport(
        task_name="Task Failed",
        total_runs=2,
        successful_runs=1,
        success_rate=0.5,
        average_duration_seconds=1.0,
        average_steps=2.0,
        total_llm_calls=1,
        trials=[],
    )

    with (
        patch("benchmarks.runner.reset_gitea"),
        patch(
            "benchmarks.orchestrator.BenchmarkOrchestrator.run",
            return_value=(mock_report, tmp_path / "result.json"),
        ),
    ):
        code = main(
            ["--task", "Task Failed", "--runs", "2", "--results-dir", str(tmp_path)]
        )
        assert code == 1
