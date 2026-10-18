"""Run a task's setup and its independent success check against the target's API (no browser, no agent).

The agent never grades itself: `check_success` asks Gitea directly whether the task's effect exists.
Requests go to 127.0.0.1 even when a task's target says localhost: on Windows, Python tries IPv6 first for
localhost and every request waits ~21 s before falling back. The browser keeps using the task's own target.

    uv run --project backend python -m benchmarks.tasks list | setup <task> | check <task>
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from benchmarks.tasks.schema import ApiCall, BenchmarkTask

DEFAULT_USER = "demo"
DEFAULT_PASSWORD = "demo-local-only"  # the local-only Gitea demo account from `just seed`
TIMEOUT_S = 15.0


class TaskSetupError(RuntimeError):
    """A setup step failed, so the trial would not start from the task's known state."""


@dataclass(frozen=True)
class Credentials:
    user: str
    password: str

    @classmethod
    def from_env(cls) -> Credentials:
        return cls(
            os.environ.get("GITEA_DEMO_USER", DEFAULT_USER),
            os.environ.get("GITEA_DEMO_PASSWORD", DEFAULT_PASSWORD),
        )


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    detail: str


def run_setup(task: BenchmarkTask, creds: Credentials | None = None) -> list[str]:
    """Bring the target to the task's starting state. Returns one line per step; raises TaskSetupError."""
    creds = creds or Credentials.from_env()
    done: list[str] = []
    if task.setup is None:
        return done
    if task.setup.command:
        result = subprocess.run(task.setup.command, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise TaskSetupError(f"setup command failed ({result.returncode}): {result.stderr.strip()[:200]}")
        done.append(f"command ok: {task.setup.command}")
    for call in task.setup.api_calls:
        status, _ = _request(task.target, call.method, call.url, call.body, creds)
        if status not in call.ok_status:
            expected = f"expected one of {call.ok_status}"
            raise TaskSetupError(f"{call.method} {call.url} returned {status}, {expected}")
        done.append(f"{call.method} {_path(call.url, creds)} -> {status}")
    return done


def check_success(task: BenchmarkTask, creds: Credentials | None = None) -> CheckResult:
    """Ask the target whether the task's effect exists. Only `api` checks are implemented."""
    creds = creds or Credentials.from_env()
    check = task.success_check
    if check.type != "api" or not isinstance(check.assertion, dict):
        return CheckResult(False, f"success_check type {check.type!r} is not supported here")
    a = check.assertion
    call = ApiCall(method=a.get("method", "GET"), url=a["url"])
    status, body = _request(task.target, call.method, call.url, None, creds)
    expected = int(a.get("expected_status", 200))
    if status != expected:
        got = f"{call.method} {_path(call.url, creds)} returned {status}"
        return CheckResult(False, f"{got}, expected {expected}")
    needle = a.get("body_contains")
    if needle is not None and _fill(str(needle), creds) not in body:
        return CheckResult(False, f"response of {_path(call.url, creds)} does not contain {needle!r}")
    return CheckResult(True, f"{call.method} {_path(call.url, creds)} -> {status}")


def _request(
    target: str, method: str, url: str, body: dict[str, object] | None, creds: Credentials
) -> tuple[int, str]:
    full = _ipv4(_absolute(target, _fill(url, creds)))
    auth = base64.b64encode(f"{creds.user}:{creds.password}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(full, data=data, method=method.upper())
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _fill(text: str, creds: Credentials) -> str:
    return text.replace("{user}", creds.user)


def _path(url: str, creds: Credentials) -> str:
    return urlsplit(_fill(url, creds)).path


def _absolute(target: str, url: str) -> str:
    return url if "://" in url else target.rstrip("/") + "/" + url.lstrip("/")


def _ipv4(url: str) -> str:
    parts = urlsplit(url)
    if parts.hostname != "localhost":
        return url
    netloc = "127.0.0.1" + (f":{parts.port}" if parts.port else "")
    return urlunsplit(parts._replace(netloc=netloc))
