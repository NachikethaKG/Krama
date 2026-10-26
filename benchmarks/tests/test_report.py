"""Tests for the benchmark reliability and performance reporting module."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.cli import main as cli_main
from benchmarks.report import main as report_main
from benchmarks.reporter.collector import (
    BenchmarkMetricsCollector,
    collect_benchmark_metrics,
    compute_median,
    compute_p90,
)
from benchmarks.reporter.generators import (
    HtmlReportGenerator,
    MarkdownReportGenerator,
)
from benchmarks.reporter.models import BenchmarkReportData, TaskMetrics


def test_compute_p90_and_median() -> None:
    # Empty lists
    assert compute_p90([]) == 0.0
    assert compute_median([]) == 0.0

    # Single item
    assert compute_p90([42.5]) == 42.5
    assert compute_median([42.5]) == 42.5

    # 10 values: 10, 20, ..., 100
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    # Linear interpolation at 0.9 * (10 - 1) = 8.1: 90 * 0.9 + 100 * 0.1 = 91.0
    assert compute_p90(values) == 91.0
    assert compute_median(values) == 55.0

    # Unsorted input should produce identical result
    unsorted_vals = [80.0, 20.0, 100.0, 10.0, 50.0, 30.0, 90.0, 40.0, 70.0, 60.0]
    assert compute_p90(unsorted_vals) == 91.0
    assert compute_median(unsorted_vals) == 55.0


def test_collector_math_and_varied_runs(tmp_path: Path) -> None:
    # 1. Multi-run successful task with explicit verifier accuracy
    task_a = {
        "task_name": "create-repo",
        "total_runs": 10,
        "successful_runs": 9,
        "success_rate": 0.9,
        "verifier_accuracy": 0.98,
        "false_alarm_rate": 0.01,
        "trials": [
            {"run_index": i, "success": True, "duration_seconds": 1.5 + (i * 0.1)}
            for i in range(1, 10)
        ]
        + [
            {
                "run_index": 10,
                "success": False,
                "duration_seconds": 3.0,
                "error_message": "Verification failed: repo not found",
            }
        ],
    }
    (tmp_path / "task_a.json").write_text(json.dumps(task_a), encoding="utf-8")

    # 2. Perfect task with 100% success
    task_b = {
        "task_name": "add-file",
        "total_runs": 5,
        "successful_runs": 5,
        "success_rate": 1.0,
        "trials": [
            {"run_index": i, "success": True, "duration_seconds": 2.0}
            for i in range(1, 6)
        ],
    }
    (tmp_path / "task_b.json").write_text(json.dumps(task_b), encoding="utf-8")

    # 3. 0% success runs (complete failure edge case)
    task_c = {
        "task_name": "failing-task",
        "total_runs": 4,
        "successful_runs": 0,
        "success_rate": 0.0,
        "trials": [
            {
                "run_index": i,
                "success": False,
                "duration_seconds": 5.0,
                "error_message": "Timeout",
            }
            for i in range(1, 5)
        ],
    }
    (tmp_path / "task_c.json").write_text(json.dumps(task_c), encoding="utf-8")

    collector = BenchmarkMetricsCollector(results_dir=tmp_path)
    data = collector.collect()

    assert data.total_tasks == 3
    assert data.overall_total_runs == 19
    assert data.overall_successful_runs == 14
    assert data.overall_failed_runs == 5

    # Overall success rate: 14 / 19 = ~0.7368
    assert round(data.overall_success_rate, 4) == round(14 / 19, 4)

    tasks_by_name = {t.task_name: t for t in data.tasks}

    # Verify task_a
    ta = tasks_by_name["create-repo"]
    assert ta.total_runs == 10
    assert ta.successful_runs == 9
    assert ta.failed_runs == 1
    assert ta.success_rate == 0.9
    assert ta.verifier_accuracy == 0.98
    assert ta.false_alarm_rate == 0.01
    assert ta.avg_latency_ms > 0
    assert ta.p90_latency_ms > ta.avg_latency_ms

    # Verify task_b
    tb = tasks_by_name["add-file"]
    assert tb.total_runs == 5
    assert tb.successful_runs == 5
    assert tb.failed_runs == 0
    assert tb.success_rate == 1.0
    assert tb.verifier_accuracy == 1.0
    assert tb.false_alarm_rate == 0.0
    assert tb.avg_latency_ms == 2000.0
    assert tb.p90_latency_ms == 2000.0

    # Verify task_c (0% success edge case)
    tc = tasks_by_name["failing-task"]
    assert tc.total_runs == 4
    assert tc.successful_runs == 0
    assert tc.failed_runs == 4
    assert tc.success_rate == 0.0


def test_markdown_and_html_generators() -> None:
    data = BenchmarkReportData(
        generated_at="2026-10-19T18:00:00Z",
        total_tasks=2,
        overall_success_rate=0.95,
        overall_verifier_accuracy=0.98,
        tasks=[
            TaskMetrics(
                task_name="create-repo",
                total_runs=10,
                successful_runs=10,
                success_rate=1.0,
                verifier_accuracy=0.98,
                false_alarm_rate=0.0,
                avg_latency_ms=1800.0,
                p90_latency_ms=2400.0,
            ),
            TaskMetrics(
                task_name="gitea-add-file",
                total_runs=10,
                successful_runs=9,
                success_rate=0.9,
                verifier_accuracy=0.96,
                false_alarm_rate=0.02,
                avg_latency_ms=3200.0,
                p90_latency_ms=4100.0,
            ),
        ],
    )

    # 1. Test Markdown Report
    md = MarkdownReportGenerator().generate(data)
    assert "# Krama Benchmark Reliability Report" in md
    assert (
        "| Task | Runs | Success Rate | Verifier Accuracy | False Alarms | Avg Latency | P90 Latency |"
        in md
    )
    assert "| create-repo | 10 | 100% | 98.0% | 0% | 1.8s | 2.4s |" in md
    assert "| gitea-add-file | 10 | 90.0% | 96.0% | 2.0% | 3.2s | 4.1s |" in md
    assert "## Latency & Execution Breakdown" in md
    assert "## Verifier Reliability & False Alarm Analysis" in md

    # 2. Test HTML Report
    html_out = HtmlReportGenerator().generate(data)
    assert "<!DOCTYPE html>" in html_out
    assert "<title>Krama Benchmark Reliability Report</title>" in html_out
    assert "Overall Success Rate" in html_out
    assert "create-repo" in html_out
    assert "gitea-add-file" in html_out
    assert "badge-success" in html_out


def test_cli_execution_writes_files(tmp_path: Path) -> None:
    results_dir = tmp_path / "input_results"
    results_dir.mkdir()
    output_dir = tmp_path / "out_reports"

    sample_task = {
        "task_name": "gitea-create-issue",
        "total_runs": 3,
        "successful_runs": 3,
        "success_rate": 1.0,
        "trials": [
            {"run_index": 1, "success": True, "duration_seconds": 2.1},
            {"run_index": 2, "success": True, "duration_seconds": 2.2},
            {"run_index": 3, "success": True, "duration_seconds": 2.3},
        ],
    }
    (results_dir / "bench.json").write_text(json.dumps(sample_task), encoding="utf-8")

    json_out = output_dir / "report.json"
    exit_code = report_main(
        [
            "--input-dir",
            str(results_dir),
            "--output-dir",
            str(output_dir),
            "--json",
            str(json_out),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "report.md").exists()
    assert (output_dir / "report.html").exists()
    assert json_out.exists()

    md_content = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "gitea-create-issue" in md_content
    assert "100%" in md_content

    html_content = (output_dir / "report.html").read_text(encoding="utf-8")
    assert "gitea-create-issue" in html_content


def test_edge_case_empty_results_directory(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    out_dir = tmp_path / "out_empty"

    exit_code = report_main(
        ["--input-dir", str(empty_dir), "--output-dir", str(out_dir)]
    )

    assert exit_code == 0
    assert (out_dir / "report.md").exists()
    assert (out_dir / "report.html").exists()

    md_content = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "No benchmark runs" in md_content

    html_content = (out_dir / "report.html").read_text(encoding="utf-8")
    assert "No Benchmark Runs Recorded" in html_content


def test_edge_case_missing_directory(tmp_path: Path) -> None:
    missing_dir = tmp_path / "does_not_exist"
    out_dir = tmp_path / "out_missing"

    exit_code = report_main(
        ["--input-dir", str(missing_dir), "--output-dir", str(out_dir)]
    )

    assert exit_code == 0
    assert (out_dir / "report.md").exists()
    assert (out_dir / "report.html").exists()


def test_edge_case_malformed_and_non_dict_json(tmp_path: Path) -> None:
    # 1. Truncated invalid JSON
    (tmp_path / "broken.json").write_text('{ "task_name": ', encoding="utf-8")
    # 2. JSON array instead of dict
    (tmp_path / "array.json").write_text("[1, 2, 3]", encoding="utf-8")
    # 3. JSON without task_name
    (tmp_path / "unrelated.json").write_text(
        json.dumps({"foo": "bar"}), encoding="utf-8"
    )
    # 4. Valid benchmark JSON
    valid_task = {
        "task_name": "valid-task",
        "total_runs": 2,
        "successful_runs": 2,
        "success_rate": 1.0,
        "trials": [{"success": True, "duration_seconds": 1.0}],
    }
    (tmp_path / "valid.json").write_text(json.dumps(valid_task), encoding="utf-8")

    data = collect_benchmark_metrics(results_dir=tmp_path)
    # The 3 invalid files should be skipped cleanly, and valid-task should be parsed
    assert data.total_tasks == 1
    assert data.tasks[0].task_name == "valid-task"


def test_standalone_verifier_accuracy_integration(tmp_path: Path) -> None:
    accuracy_file = {
        "verifier_name": "LayeredVerifier",
        "total_cases": 20,
        "detection_accuracy": 0.95,
        "false_alarm_rate": 0.05,
        "true_positives": 10,
        "false_positives": 1,
    }
    (tmp_path / "verifier-accuracy-20261010.json").write_text(
        json.dumps(accuracy_file), encoding="utf-8"
    )

    task_file = {
        "task_name": "gitea-task",
        "total_runs": 5,
        "successful_runs": 5,
        "trials": [{"success": True, "duration_seconds": 2.0} for _ in range(5)],
    }
    (tmp_path / "task.json").write_text(json.dumps(task_file), encoding="utf-8")

    data = collect_benchmark_metrics(results_dir=tmp_path)
    assert data.total_tasks == 1
    assert data.overall_verifier_accuracy == 0.95
    assert data.overall_false_alarm_rate == 0.05


def test_cli_routing(tmp_path: Path) -> None:
    # Test unified benchmarks.cli routing
    results_dir = tmp_path / "res"
    results_dir.mkdir()
    (results_dir / "t.json").write_text(
        json.dumps({"task_name": "t1", "total_runs": 1, "successful_runs": 1}),
        encoding="utf-8",
    )
    out_dir = tmp_path / "out"

    # Route via 'report' subcommand
    ret = cli_main(
        ["report", "--input-dir", str(results_dir), "--output-dir", str(out_dir)]
    )
    assert ret == 0
    assert (out_dir / "report.md").exists()


def test_recovery_rate_and_multi_platform_metrics(tmp_path: Path) -> None:
    gitea_task = {
        "task_name": "gitea-create-issue",
        "platform": "gitea",
        "total_runs": 2,
        "successful_runs": 2,
        "trials": [
            {
                "run_index": 1,
                "success": True,
                "duration_seconds": 15.0,
                "planning_duration_seconds": 3.2,
                "replan_attempts": 1,
                "replan_successes": 1,
            },
            {
                "run_index": 2,
                "success": True,
                "duration_seconds": 14.0,
                "planning_duration_seconds": 2.8,
                "replan_attempts": 0,
                "replan_successes": 0,
            },
        ],
    }
    github_task = {
        "task_name": "github-create-repo",
        "platform": "github",
        "total_runs": 2,
        "successful_runs": 2,
        "trials": [
            {
                "run_index": 1,
                "success": True,
                "duration_seconds": 22.0,
                "planning_duration_seconds": 4.5,
                "replan_attempts": 2,
                "replan_successes": 1,
            },
            {
                "run_index": 2,
                "success": True,
                "duration_seconds": 20.0,
                "planning_duration_seconds": 4.1,
                "replan_attempts": 0,
                "replan_successes": 0,
            },
        ],
    }
    (tmp_path / "gitea.json").write_text(json.dumps(gitea_task), encoding="utf-8")
    (tmp_path / "github.json").write_text(json.dumps(github_task), encoding="utf-8")

    data = collect_benchmark_metrics(results_dir=tmp_path)
    assert data.total_tasks == 2
    tasks = {t.task_name: t for t in data.tasks}

    # Gitea task validation
    gt = tasks["gitea-create-issue"]
    assert gt.platform == "gitea"
    assert gt.replan_attempts == 1
    assert gt.replan_successes == 1
    assert gt.recovery_rate == 100.0
    assert gt.avg_planning_latency_ms == 3000.0

    # GitHub task validation
    gh = tasks["github-create-repo"]
    assert gh.platform == "github"
    assert gh.replan_attempts == 2
    assert gh.replan_successes == 1
    assert gh.recovery_rate == 50.0
    assert gh.avg_planning_latency_ms == 4300.0

    # Overall recovery rate: (1 + 1) / (1 + 2) * 100 = 66.67%
    assert data.overall_replan_attempts == 3
    assert data.overall_replan_successes == 2
    assert data.overall_recovery_rate == 66.67
    assert data.overall_avg_planning_latency_ms > 0
    assert data.overall_p50_latency_ms > 0

    # Test contract dict serialization
    contract_dict = data.to_contract_dict()
    assert contract_dict["total_tasks"] == 2
    assert "platform" not in contract_dict["tasks"][0]  # contract forbid extra
