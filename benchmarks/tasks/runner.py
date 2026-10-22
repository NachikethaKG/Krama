"""Run a task's setup and its independent success check against the target's API (no browser, no agent).

The agent never grades itself: `check_success` asks the site's own API (Gitea, or GitHub with the test
account's token) whether the task's effect exists.
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
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from benchmarks.tasks.schema import ApiCall, BenchmarkTask

DEFAULT_USER = "demo"
DEFAULT_PASSWORD = "demo-local-only"  # the local-only Gitea demo account from `just seed`
TIMEOUT_S = 15.0
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class TaskSetupError(RuntimeError):
    """A setup step failed, so the trial would not start from the task's known state."""


@dataclass(frozen=True)
class Credentials:
    user: str
    password: str = ""
    token: str = ""
    """A bearer token (GitHub). When set it is sent instead of basic auth."""
    org: str = ""

    @classmethod
    def from_env(cls) -> Credentials:
        return cls(
            os.environ.get("GITEA_DEMO_USER", DEFAULT_USER),
            os.environ.get("GITEA_DEMO_PASSWORD", DEFAULT_PASSWORD),
        )

    @classmethod
    def github_from_env(cls) -> Credentials:
        """The GitHub test account (docs/research/phase-3-together-github-account-and-benchmarks.md)."""
        env = {**_dotenv(), **os.environ}
        token, org = env.get("GITHUB_BENCH_TOKEN", ""), env.get("GITHUB_TEST_ORG", "")
        if not token or not org:
            raise TaskSetupError("GITHUB_BENCH_TOKEN and GITHUB_TEST_ORG must be set (.env) for GitHub tasks")
        return cls(user=env.get("GITHUB_TEST_USER", ""), token=token, org=org)

    @classmethod
    def for_task(cls, task: BenchmarkTask) -> Credentials:
        return cls.github_from_env() if task.site == "github" else cls.from_env()


def _dotenv() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    pairs = (line.split("=", 1) for line in ENV_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {k.strip(): v.strip().strip('"') for k, v in pairs if not k.lstrip().startswith("#")}


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    detail: str


def run_setup(task: BenchmarkTask, creds: Credentials | None = None) -> list[str]:
    """Bring the target to the task's starting state. Returns one line per step; raises TaskSetupError."""
    creds = creds or Credentials.for_task(task)
    done: list[str] = []
    if task.setup is None:
        return done
    if task.setup.command:
        result = subprocess.run(task.setup.command, shell=True, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise TaskSetupError(f"setup command failed ({result.returncode}): {result.stderr.strip()[:200]}")
        done.append(f"command ok: {task.setup.command}")
    for call in task.setup.api_calls:
        status, _ = _request(_api(task), call.method, call.url, call.body, creds)
        if status not in call.ok_status:
            expected = f"expected one of {call.ok_status}"
            raise TaskSetupError(f"{call.method} {call.url} returned {status}, {expected}")
        done.append(f"{call.method} {_path(call.url, creds)} -> {status}")
    return done


def check_success(task: BenchmarkTask, creds: Credentials | None = None) -> CheckResult:
    """Ask the target whether the task's effect exists. Only `api` checks are implemented."""
    creds = creds or Credentials.for_task(task)
    check = task.success_check
    if check.type != "api" or not isinstance(check.assertion, dict):
        return CheckResult(False, f"success_check type {check.type!r} is not supported here")
    a = check.assertion
    call = ApiCall(method=a.get("method", "GET"), url=a["url"])
    status, body = _request(_api(task), call.method, call.url, None, creds, accept=a.get("accept"))
    expected = int(a.get("expected_status", 200))
    if status != expected:
        got = f"{call.method} {_path(call.url, creds)} returned {status}"
        return CheckResult(False, f"{got}, expected {expected}")
    needles = a.get("body_contains")
    for needle in needles if isinstance(needles, list) else [] if needles is None else [needles]:
        if _fill(str(needle), creds) not in body:
            return CheckResult(False, f"response of {_path(call.url, creds)} does not contain {needle!r}")
    return CheckResult(True, f"{call.method} {_path(call.url, creds)} -> {status}")


def _api(task: BenchmarkTask) -> str:
    return task.api_base or task.target


def _request(
    target: str,
    method: str,
    url: str,
    body: dict[str, object] | None,
    creds: Credentials,
    accept: str | None = None,
) -> tuple[int, str]:
    full = _ipv4(_absolute(target, _fill(url, creds)))
    data = json.dumps(_fill_json(body, creds)).encode() if body is not None else None
    req = urllib.request.Request(full, data=data, method=method.upper())
    if creds.token:
        req.add_header("Authorization", f"Bearer {creds.token}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
    else:
        auth = base64.b64encode(f"{creds.user}:{creds.password}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Accept", accept or "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _fill(text: str, creds: Credentials) -> str:
    return text.replace("{user}", creds.user).replace("{org}", creds.org)


def _fill_json(value: object, creds: Credentials) -> object:
    """Placeholders inside a request body too (e.g. a repo name under the org)."""
    if isinstance(value, str):
        return _fill(value, creds)
    if isinstance(value, dict):
        return {k: _fill_json(v, creds) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill_json(v, creds) for v in value]
    return value


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
