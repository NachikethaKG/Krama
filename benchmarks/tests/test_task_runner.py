"""Task setup and success checks (benchmarks/tasks/runner.py), against a tiny local HTTP server."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from benchmarks.tasks.runner import Credentials, TaskSetupError, _ipv4, check_success, run_setup
from benchmarks.tasks.schema import BenchmarkTask, load_all_tasks

CREDS = Credentials("demo", "pw")


class FakeApi:
    """Answers every request with the status/body registered for its method and path; records the calls."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], tuple[int, str]] = {}
        self.calls: list[tuple[str, str, dict[str, Any] | None, str | None]] = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                api.calls.append((self.command, self.path, body, self.headers.get("Authorization")))
                status, text = api.routes.get((self.command, self.path), (404, "{}"))
                self.send_response(status)
                self.end_headers()
                self.wfile.write(text.encode())

            do_GET = do_POST = do_DELETE = do_PATCH = _answer

            def log_message(self, *args: object) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        # localhost on purpose: the runner must send it to 127.0.0.1
        self.target = f"http://localhost:{self.server.server_port}"


@pytest.fixture
def api() -> Iterator[FakeApi]:
    fake = FakeApi()
    thread = threading.Thread(target=fake.server.serve_forever, daemon=True)
    thread.start()
    yield fake
    fake.server.shutdown()


def task(target: str, check: dict[str, Any], calls: list[dict[str, Any]] | None = None) -> BenchmarkTask:
    return BenchmarkTask.model_validate(
        {
            "name": "t",
            "prompt": "p",
            "target": target,
            "setup": {"api_calls": calls or []},
            "success_check": {"type": "api", "assertion": check},
        }
    )


def test_every_task_file_loads_and_the_new_ones_reset_and_check_through_the_api() -> None:
    tasks = {t.name: t for t in load_all_tasks()}

    new = ["gitea-create-issue", "gitea-create-branch", "gitea-add-file", "gitea-repo-settings"]
    assert set(new) <= set(tasks)
    for name in new:
        t = tasks[name]
        assert t.target == "http://localhost:3001"
        assert t.setup is not None and [c.method for c in t.setup.api_calls] == ["DELETE", "POST"]
        assert 404 in t.setup.api_calls[0].ok_status  # the repo may not exist yet
        assert t.success_check.type == "api" and isinstance(t.success_check.assertion, dict)
        assert t.success_check.assertion["url"].startswith("/api/v1/repos/{user}/")


def test_setup_runs_the_calls_in_order_as_the_demo_user(api: FakeApi) -> None:
    api.routes[("POST", "/api/v1/user/repos")] = (201, "{}")
    calls: list[dict[str, Any]] = [
        {"method": "DELETE", "url": "/api/v1/repos/{user}/r", "ok_status": [204, 404]},
        {"method": "POST", "url": "/api/v1/user/repos", "body": {"name": "r"}, "ok_status": [201]},
    ]

    done = run_setup(task(api.target, {"url": "/x"}, calls), CREDS)

    assert done == ["DELETE /api/v1/repos/demo/r -> 404", "POST /api/v1/user/repos -> 201"]
    assert [(m, p, b) for m, p, b, _ in api.calls] == [
        ("DELETE", "/api/v1/repos/demo/r", None),
        ("POST", "/api/v1/user/repos", {"name": "r"}),
    ]
    assert all(auth and auth.startswith("Basic ") for *_, auth in api.calls)


def test_setup_stops_on_an_unexpected_status(api: FakeApi) -> None:
    calls: list[dict[str, Any]] = [{"method": "POST", "url": "/api/v1/user/repos", "ok_status": [201]}]

    with pytest.raises(TaskSetupError, match="returned 404"):
        run_setup(task(api.target, {"url": "/x"}, calls), CREDS)


def test_check_passes_only_with_the_status_and_the_text(api: FakeApi) -> None:
    api.routes[("GET", "/api/v1/repos/demo/r")] = (200, '{"description":"Docs for the team"}')
    url = "/api/v1/repos/{user}/r"

    assert check_success(task(api.target, {"url": url, "body_contains": "Docs for the team"}), CREDS).passed
    missing = check_success(task(api.target, {"url": url, "body_contains": "Other"}), CREDS)
    assert not missing.passed and "does not contain" in missing.detail
    wrong = check_success(task(api.target, {"url": "/api/v1/repos/{user}/gone"}), CREDS)
    assert not wrong.passed and "returned 404" in wrong.detail


def test_only_api_checks_are_supported() -> None:
    t = BenchmarkTask.model_validate(
        {
            "name": "t",
            "prompt": "p",
            "target": "http://x",
            "success_check": {"type": "dom", "assertion": "h1"},
        }
    )

    assert not check_success(t, CREDS).passed


def test_localhost_is_sent_to_ipv4() -> None:
    # On Windows, localhost tries IPv6 first and each request waits ~21 s.
    assert _ipv4("http://localhost:3001/api/v1/x?y=1") == "http://127.0.0.1:3001/api/v1/x?y=1"
    assert _ipv4("http://gitea.example:3001/a") == "http://gitea.example:3001/a"
