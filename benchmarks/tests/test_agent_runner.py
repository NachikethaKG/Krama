import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from benchmarks.agent_runner import (
    AgentRunner,
    extract_metrics_from_log,
    find_run_log_path,
)


def test_extract_metrics_from_valid_log(tmp_path: Path) -> None:
    log_file = tmp_path / "run-log.json"
    content = {
        "status": "verified",
        "duration_ms": 3200,
        "message": "every step verified",
        "steps": [
            {"seq": 1, "verify_attempts": 1},
            {"seq": 2, "verify_attempts": 3},  # 2 retries
            {"seq": 3, "verify_attempts": 1},
        ],
        "llm_attempts": [
            {"model": "gemini-2.5-flash", "tokens_in": 150, "tokens_out": 40},
            {"model": "gemini-2.5-flash", "tokens_in": 200, "tokens_out": 50},
        ],
    }
    log_file.write_text(json.dumps(content), encoding="utf-8")

    metrics = extract_metrics_from_log(log_file)
    assert metrics["success"] is True
    assert metrics["duration_seconds"] == 3.2
    assert metrics["steps_taken"] == 3
    assert metrics["retries_count"] == 2
    assert metrics["llm_call_count"] == 2
    assert metrics["tokens_in"] == 350
    assert metrics["tokens_out"] == 90
    assert metrics["error_message"] is None


def test_extract_metrics_from_failed_log(tmp_path: Path) -> None:
    log_file = tmp_path / "run-log.json"
    content = {
        "status": "failed",
        "duration_ms": 1500,
        "message": "target_not_found: Button 'Save' not located",
        "steps": [{"seq": 1, "verify_attempts": 1}],
        "llm_attempts": [],
    }
    log_file.write_text(json.dumps(content), encoding="utf-8")

    metrics = extract_metrics_from_log(log_file)
    assert metrics["success"] is False
    assert metrics["duration_seconds"] == 1.5
    assert metrics["steps_taken"] == 1
    assert metrics["retries_count"] == 0
    assert metrics["llm_call_count"] == 0
    assert "target_not_found" in str(metrics["error_message"])


def test_find_run_log_path(tmp_path: Path) -> None:
    log_file = tmp_path / "run-log.json"
    log_file.write_text("{}", encoding="utf-8")

    stdout = f"VERIFIED: done (1200 ms, 1 LLM request(s))\nRun log: {log_file}\nRecording: none"
    found = find_run_log_path(stdout)
    assert found == log_file

    missing = find_run_log_path("No run log generated here.")
    assert missing is None


def test_agent_runner_happy_path(tmp_path: Path) -> None:
    log_file = tmp_path / "run-log.json"
    content = {
        "status": "verified",
        "duration_ms": 2500,
        "steps": [{"seq": 1, "verify_attempts": 1}, {"seq": 2, "verify_attempts": 1}],
        "llm_attempts": [{"model": "fake", "tokens_in": 100, "tokens_out": 20}],
    }
    log_file.write_text(json.dumps(content), encoding="utf-8")

    stdout = f"VERIFIED: done\nRun log: {log_file}\n"
    fake_completed = subprocess.CompletedProcess(
        args=["krama", "run"],
        returncode=0,
        stdout=stdout,
        stderr="",
    )

    runner = AgentRunner()
    with patch("subprocess.run", return_value=fake_completed):
        trial = runner.run(run_index=1, task="Create test repo")

    assert trial.run_index == 1
    assert trial.success is True
    assert trial.duration_seconds == 2.5
    assert trial.steps_taken == 2
    assert trial.retries_count == 0
    assert trial.llm_call_count == 1
    assert trial.tokens_in == 100
    assert trial.tokens_out == 20
    assert trial.error_message is None


def test_agent_runner_process_failure_exit_code() -> None:
    fake_failed = subprocess.CompletedProcess(
        args=["krama", "run"],
        returncode=1,
        stdout="FAILED: Step 2 could not be verified\n",
        stderr="Traceback / Error message",
    )

    runner = AgentRunner()
    with patch("subprocess.run", return_value=fake_failed):
        trial = runner.run(run_index=2, task="Create test repo")

    assert trial.run_index == 2
    assert trial.success is False
    assert trial.error_message is not None
    assert "Traceback" in trial.error_message or "FAILED" in trial.error_message


def test_agent_runner_timeout_handled_gracefully() -> None:
    def fake_timeout(
        *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=["krama", "run"], timeout=5.0)

    runner = AgentRunner(timeout=5.0)
    with patch("subprocess.run", side_effect=fake_timeout):
        trial = runner.run(run_index=3, task="Slow task")

    assert trial.run_index == 3
    assert trial.success is False
    assert trial.error_message is not None
    assert "timed out after 5.0s" in trial.error_message
