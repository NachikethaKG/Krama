from datetime import UTC, datetime
from pathlib import Path

from benchmarks.collector import MetricsCollector
from benchmarks.models import BenchmarkReport, RunTrial


def test_run_trial_creation_and_serialization() -> None:
    trial = RunTrial(
        run_index=1,
        success=True,
        duration_seconds=12.5,
        steps_taken=4,
        retries_count=1,
        llm_call_count=3,
        tokens_in=500,
        tokens_out=150,
        error_message=None,
    )
    raw_json = trial.model_dump_json()
    loaded = RunTrial.model_validate_json(raw_json)
    assert loaded.run_index == 1
    assert loaded.success is True
    assert loaded.duration_seconds == 12.5
    assert loaded.steps_taken == 4
    assert loaded.retries_count == 1
    assert loaded.llm_call_count == 3
    assert loaded.tokens_in == 500
    assert loaded.tokens_out == 150
    assert loaded.error_message is None


def test_metrics_collector_empty() -> None:
    collector = MetricsCollector(task_name="Empty task")
    report = collector.aggregate()
    assert report.task_name == "Empty task"
    assert report.total_runs == 0
    assert report.successful_runs == 0
    assert report.success_rate == 0.0
    assert report.average_duration_seconds == 0.0
    assert report.average_steps == 0.0
    assert report.min_steps == 0
    assert report.max_steps == 0
    assert report.total_llm_calls == 0


def test_metrics_collector_aggregation_math() -> None:
    collector = MetricsCollector(task_name="Test task")
    collector.record_trial(
        RunTrial(
            run_index=1,
            success=True,
            duration_seconds=10.0,
            steps_taken=4,
            retries_count=0,
            llm_call_count=2,
            tokens_in=300,
            tokens_out=100,
        )
    )
    collector.record_trial(
        RunTrial(
            run_index=2,
            success=False,
            duration_seconds=20.0,
            steps_taken=2,
            retries_count=2,
            llm_call_count=4,
            tokens_in=600,
            tokens_out=200,
            error_message="Step verification timeout",
        )
    )

    report = collector.aggregate()
    assert report.task_name == "Test task"
    assert report.total_runs == 2
    assert report.successful_runs == 1
    assert report.success_rate == 0.5
    assert report.average_duration_seconds == 15.0
    assert report.average_steps == 3.0
    assert report.min_steps == 2
    assert report.max_steps == 4
    assert report.total_llm_calls == 6
    assert report.total_retries == 2
    assert report.total_tokens_in == 900
    assert report.total_tokens_out == 300
    assert report.total_duration_seconds == 30.0


def test_save_report_persists_json(tmp_path: Path) -> None:
    collector = MetricsCollector(task_name="Create Repo / Demo!")
    collector.record_trial(
        RunTrial(
            run_index=1,
            success=True,
            duration_seconds=5.0,
            steps_taken=3,
            retries_count=0,
            llm_call_count=1,
        )
    )
    fixed_time = datetime(2026, 10, 9, 12, 0, 0, tzinfo=UTC)
    report = collector.aggregate(timestamp=fixed_time)
    saved_file = collector.save_report(report, results_dir=tmp_path, timestamp=fixed_time)

    assert saved_file.exists()
    assert saved_file.name == "create_repo_demo_20261009_120000.json"

    loaded = BenchmarkReport.model_validate_json(saved_file.read_text(encoding="utf-8"))
    assert loaded.task_name == "Create Repo / Demo!"
    assert loaded.total_runs == 1
    assert loaded.successful_runs == 1
    assert loaded.success_rate == 1.0
    assert len(loaded.trials) == 1
