"""Task-file benchmarks (#83): each trial starts from the task's setup and is graded by its success_check,
not by the agent; and the API runner drives the real product path."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from benchmarks.api_runner import ApiAgentRunner
from benchmarks.models import RunTrial
from benchmarks.orchestrator import BenchmarkOrchestrator
from benchmarks.tasks.runner import CheckResult, TaskSetupError
from benchmarks.tasks.schema import BenchmarkTask

SPEC = BenchmarkTask.model_validate(
    {
        "name": "gitea-create-issue",
        "prompt": "Open an issue",
        "target": "http://localhost:3001",
        "success_check": {"type": "api", "assertion": {"url": "/x"}},
    }
)


class ScriptedRunner:
    def __init__(self, verified: list[bool]) -> None:
        self.verified = verified
        self.tasks: list[str] = []

    def run(self, run_index: int, task: str) -> RunTrial:
        self.tasks.append(task)
        ok = self.verified[run_index - 1]
        return RunTrial(run_index=run_index, success=ok, duration_seconds=1, steps_taken=3, retries_count=0,
                        llm_call_count=1)  # fmt: skip


def test_a_trial_counts_only_if_the_independent_check_passes(tmp_path: Path) -> None:
    runner = ScriptedRunner([True, True, False])
    checks = iter([CheckResult(True, "200"), CheckResult(False, "returned 404"), CheckResult(True, "200")])

    with (
        patch("benchmarks.orchestrator.run_setup", return_value=[]) as setup,
        patch("benchmarks.orchestrator.check_success", side_effect=lambda _spec: next(checks)),
    ):
        report, _ = BenchmarkOrchestrator(
            task="", runs=3, runner=runner, results_dir=tmp_path, spec=SPEC
        ).run()

    assert setup.call_count == 3 and runner.tasks == ["Open an issue"] * 3
    assert report.task_name == "gitea-create-issue"
    assert [t.success for t in report.trials] == [True, False, True]
    # Trial 2: the agent said verified but nothing was created: a verifier false positive, now visible.
    assert [t.agent_verified for t in report.trials] == [True, True, False]
    assert report.trials[1].independent_check == "returned 404"


def test_a_failed_setup_is_a_failed_trial_not_a_crash(tmp_path: Path) -> None:
    runner = ScriptedRunner([True])

    with patch("benchmarks.orchestrator.run_setup", side_effect=TaskSetupError("POST returned 500")):
        report, _ = BenchmarkOrchestrator(
            task="", runs=1, runner=runner, results_dir=tmp_path, spec=SPEC
        ).run()

    assert runner.tasks == [] and not report.trials[0].success
    assert "POST returned 500" in (report.trials[0].error_message or "")


class FakeApi:
    """The backend API, scripted: a task plans, its plan is approved, the run ends with `final`."""

    def __init__(self, final: str, planned: str = "planned") -> None:
        self.calls: list[str] = []
        self.seen: list[tuple[str | None, str | None]] = []
        """(X-Krama header, Cookie header) of every request after the sign-in (#94)."""
        state = {"final": final, "planned": planned}
        calls, seen = self.calls, self.seen

        class Handler(BaseHTTPRequestHandler):
            def _send(self, body: dict[str, Any]) -> None:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_POST(self) -> None:
                calls.append(f"POST {self.path}")
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path == "/api/v1/auth/login":
                    self.send_response(200)
                    self.send_header("Set-Cookie", "krama_session=s3cret; Path=/; HttpOnly")
                    self.end_headers()
                    self.wfile.write(b'{"id": "u1", "email": "demo@krama.dev"}')
                    return
                seen.append((self.headers.get("X-Krama"), self.headers.get("Cookie")))
                if self.path == "/api/v1/tasks":
                    self._send({"id": "t1", "status": "planning"})
                elif self.path.endswith("/approve"):
                    self._send({"id": "r1", "status": "queued"})
                else:  # cancel
                    self._send({"id": "r1", "status": "cancelled"})

            def do_GET(self) -> None:
                calls.append(f"GET {self.path}")
                seen.append((self.headers.get("X-Krama"), self.headers.get("Cookie")))
                if self.path == "/api/v1/tasks/t1":
                    self._send({"id": "t1", "status": state["planned"], "plan_id": "p1",
                                "clarification_question": "Which repo?"})  # fmt: skip
                elif self.path == "/api/v1/plans/p1":
                    self._send({"id": "p1", "revision": 1})
                else:
                    error = {"message": "Step 3 no longer works"} if state["final"] == "failed" else None
                    self._send({"id": "r1", "status": state["final"], "current_seq": 3, "retry_count": 1,
                                "error": error})  # fmt: skip

            def log_message(self, *args: object) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/api/v1"


@pytest.fixture
def api_for() -> Iterator[Any]:
    servers: list[HTTPServer] = []

    def make(final: str, planned: str = "planned") -> tuple[FakeApi, ApiAgentRunner]:
        fake = FakeApi(final, planned)
        servers.append(fake.server)
        threading.Thread(target=fake.server.serve_forever, daemon=True).start()
        return fake, ApiAgentRunner(api_url=fake.url, timeout=10, poll_s=0.01)

    yield make
    for server in servers:
        server.shutdown()


def test_api_runner_reports_a_verified_run(api_for: Any) -> None:
    fake, runner = api_for("verified")

    trial = runner.run(1, "Open an issue")

    assert trial.success and trial.steps_taken == 3 and trial.retries_count == 1
    assert "POST /api/v1/plans/p1/approve" in fake.calls


def test_api_runner_signs_in_once_and_sends_the_cookie_and_csrf_header(api_for: Any) -> None:
    # #94: the API needs a session cookie, and X-Krama: 1 on changes.
    fake, runner = api_for("verified")

    runner.run(1, "Open an issue")
    runner.run(2, "Open an issue")

    assert fake.calls[0] == "POST /api/v1/auth/login"
    assert fake.calls.count("POST /api/v1/auth/login") == 1
    assert fake.seen
    assert all(header == "1" and cookie == "krama_session=s3cret" for header, cookie in fake.seen)


def test_api_runner_cancels_a_paused_run_and_fails_the_trial(api_for: Any) -> None:
    fake, runner = api_for("paused")

    trial = runner.run(1, "Open an issue")

    assert not trial.success and "paused" in (trial.error_message or "")
    assert fake.calls[-1] == "POST /api/v1/runs/r1/cancel"  # frees the only run slot for the next trial


def test_api_runner_reports_failures_and_unplanned_tasks(api_for: Any) -> None:
    _, failing = api_for("failed")
    _, unclear = api_for("verified", planned="needs_clarification")

    assert failing.run(1, "x").error_message == "Step 3 no longer works"
    trial = unclear.run(1, "x")
    assert not trial.success and "needs_clarification" in (trial.error_message or "")
