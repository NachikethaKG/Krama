"""Subprocess CLI wrapper for black-box agent execution.

Executes the Krama agent strictly through its public CLI interface,
captures output, and extracts run metrics without touching internal classes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from benchmarks.models import RunTrial


class AgentProcessError(Exception):
    """Raised when the agent CLI execution encounters a system error."""


def extract_metrics_from_log(log_path: Path) -> dict[str, int | float | bool | str | None]:
    """Parse a written run-log.json artifact and extract benchmark metrics."""
    data = json.loads(log_path.read_text(encoding="utf-8"))
    status = data.get("status", "error")
    is_ok = status == "verified"

    steps = data.get("steps", [])
    steps_taken = len(steps)
    retries_count = sum(max(0, s.get("verify_attempts", 1) - 1) for s in steps)

    llm_attempts = data.get("llm_attempts", [])
    llm_call_count = len(llm_attempts)
    tokens_in = sum(a.get("tokens_in") or 0 for a in llm_attempts)
    tokens_out = sum(a.get("tokens_out") or 0 for a in llm_attempts)

    duration_ms = data.get("duration_ms")
    duration_seconds = (duration_ms / 1000.0) if duration_ms is not None else 0.0

    error_msg = None if is_ok else (data.get("message") or f"Run status: {status}")

    return {
        "success": is_ok,
        "duration_seconds": duration_seconds,
        "steps_taken": steps_taken,
        "retries_count": retries_count,
        "llm_call_count": llm_call_count,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "error_message": error_msg,
    }


def find_run_log_path(stdout: str) -> Path | None:
    """Find the path of the generated run-log.json from CLI stdout."""
    match = re.search(r"Run log:\s*([^\r\n]+)", stdout)
    if match:
        p = Path(match.group(1).strip())
        if p.exists():
            return p
    return None


class AgentRunner:
    """Invokes the agent via subprocess and parses the resulting execution metrics."""

    def __init__(
        self,
        target_url: str = "http://localhost:3001",
        site: str | None = "gitea",
        login: bool = True,
        auto_approve: bool = True,
        timeout: float = 300.0,
        repo_root: Path | None = None,
        custom_cmd: list[str] | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> None:
        self.target_url = target_url
        self.site = site
        self.login = login
        self.auto_approve = auto_approve
        self.timeout = timeout
        self.repo_root = repo_root or Path(__file__).resolve().parents[1]
        self.custom_cmd = custom_cmd
        self.env_overrides = env_overrides or {}

    def build_command(self, task: str) -> list[str]:
        """Construct the CLI command for the given task."""
        if self.custom_cmd:
            return [*self.custom_cmd, task]

        cmd = [
            sys.executable,
            "-m",
            "app.cli",
            "run",
            task,
            "--target",
            self.target_url,
        ]
        if self.site:
            cmd.extend(["--site", self.site])
        if self.login:
            cmd.append("--login")
        if self.auto_approve:
            cmd.append("--yes")
        return cmd

    def run(self, run_index: int, task: str) -> RunTrial:
        """Execute a single trial of the agent via subprocess and return its RunTrial."""
        cmd = self.build_command(task)

        env = os.environ.copy()
        backend_dir = str(self.repo_root / "backend")
        current_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{backend_dir}{os.pathsep}{current_pythonpath}" if current_pythonpath else backend_dir
        )
        env.update(self.env_overrides)

        start_time = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                check=False,
            )
            wall_clock = time.perf_counter() - start_time
        except subprocess.TimeoutExpired as exc:
            wall_clock = time.perf_counter() - start_time
            return RunTrial(
                run_index=run_index,
                success=False,
                duration_seconds=round(wall_clock, 3),
                steps_taken=0,
                retries_count=0,
                llm_call_count=0,
                error_message=f"Agent subprocess timed out after {self.timeout}s: {exc}",
            )
        except (OSError, RuntimeError) as exc:
            wall_clock = time.perf_counter() - start_time
            return RunTrial(
                run_index=run_index,
                success=False,
                duration_seconds=round(wall_clock, 3),
                steps_taken=0,
                retries_count=0,
                llm_call_count=0,
                error_message=f"Agent subprocess execution failed: {exc}",
            )

        log_path = find_run_log_path(result.stdout)
        if log_path is not None:
            try:
                metrics = extract_metrics_from_log(log_path)
                return RunTrial(
                    run_index=run_index,
                    success=bool(metrics["success"]) and result.returncode == 0,
                    duration_seconds=round(float(metrics["duration_seconds"] or wall_clock), 3),
                    steps_taken=int(metrics["steps_taken"] or 0),
                    retries_count=int(metrics["retries_count"] or 0),
                    llm_call_count=int(metrics["llm_call_count"] or 0),
                    tokens_in=int(metrics["tokens_in"] or 0),
                    tokens_out=int(metrics["tokens_out"] or 0),
                    error_message=str(metrics["error_message"])
                    if metrics["error_message"]
                    else (None if result.returncode == 0 else f"Process exited with code {result.returncode}"),
                )
            except (json.JSONDecodeError, OSError, KeyError, ValueError):
                pass

        # Fallback if no run-log.json was written (e.g. process crash or early exit)
        is_success = result.returncode == 0
        error_msg = None
        if not is_success:
            error_msg = result.stderr.strip() or result.stdout.strip() or f"Exited with code {result.returncode}"

        return RunTrial(
            run_index=run_index,
            success=is_success,
            duration_seconds=round(wall_clock, 3),
            steps_taken=0,
            retries_count=0,
            llm_call_count=0,
            error_message=error_msg,
        )
