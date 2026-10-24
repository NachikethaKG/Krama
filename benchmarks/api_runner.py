"""Benchmark trials through the running backend API, the product path (#83).

`AgentRunner` runs the old `krama run` CLI loop, which has no Safety Policy, no recovery and no database. This
runner does what a user does: sign in, POST /tasks, approve the plan, wait for the run. Nobody answers a pause
in a benchmark, so a paused run is cancelled and counts as not done. Start the API first (`just backend dev`).

Sign-in (#94): as KRAMA_BENCH_EMAIL / KRAMA_BENCH_PASSWORD, else the seeded demo@krama.dev with
KRAMA_DEMO_PASSWORD (environment or the repo-root .env). Every call sends X-Krama: 1 (the API's CSRF check).
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from benchmarks.models import RunTrial

FINAL = ("verified", "failed", "cancelled")
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEMO_EMAIL = "demo@krama.dev"


class ApiAgentRunner:
    def __init__(
        self,
        target_url: str = "http://localhost:3001",
        api_url: str = "http://127.0.0.1:8000/api/v1",
        timeout: float = 300.0,
        poll_s: float = 1.0,
    ) -> None:
        self.target_url = target_url
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.poll_s = poll_s
        # Keeps the session cookie between calls, like a browser.
        cookies = urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        self._opener = urllib.request.build_opener(cookies)
        self._signed_in = False

    def run(self, run_index: int, task: str) -> RunTrial:
        t0 = time.perf_counter()

        def trial(success: bool, error: str | None = None, run: dict[str, Any] | None = None) -> RunTrial:
            return RunTrial(
                run_index=run_index,
                success=success,
                duration_seconds=round(time.perf_counter() - t0, 2),
                steps_taken=int((run or {}).get("current_seq") or 0),
                retries_count=int((run or {}).get("retry_count") or 0),
                llm_call_count=0,  # not exposed by the API
                error_message=error,
            )

        try:
            self._sign_in()
            created = self._call("POST", "/tasks", {"prompt": task, "target_url": self.target_url})
            planned = self._wait(f"/tasks/{created['id']}", lambda t: t["status"] != "planning", t0)
            if planned["status"] != "planned":
                why = planned.get("clarification_question") or planned.get("error")
                return trial(False, f"planning {planned['status']}: {why}")
            plan = self._call("GET", f"/plans/{planned['plan_id']}")
            run = self._call("POST", f"/plans/{plan['id']}/approve", {"revision": plan["revision"]})
            run = self._wait(f"/runs/{run['id']}", lambda r: r["status"] in (*FINAL, "paused"), t0)
            if run["status"] == "paused":
                self._call("POST", f"/runs/{run['id']}/cancel")
                return trial(False, "paused for a human (cancelled: nobody answers in a benchmark)", run)
            error = (run.get("error") or {}).get("message")
            return trial(run["status"] == "verified", error, run)
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            return trial(False, f"{type(e).__name__}: {e}")

    def _wait(self, path: str, done: Any, t0: float) -> dict[str, Any]:
        while True:
            body = self._call("GET", path)
            if done(body):
                return body
            if time.perf_counter() - t0 > self.timeout:
                raise TimeoutError(f"{path} not done after {self.timeout:g} s")
            time.sleep(self.poll_s)

    def _sign_in(self) -> None:
        """Once per runner. An API without accounts (before #94) answers 404 and needs none."""
        if self._signed_in:
            return
        env = {**_dotenv(), **os.environ}
        email = env.get("KRAMA_BENCH_EMAIL") or DEMO_EMAIL
        password = env.get("KRAMA_BENCH_PASSWORD") or env.get("KRAMA_DEMO_PASSWORD") or ""
        try:
            self._call("POST", "/auth/login", {"email": email, "password": password})
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise ValueError(f"benchmark sign-in as {email} failed: HTTP {e.code}") from None
        self._signed_in = True

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.api_url + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Krama", "1")
        with self._opener.open(request, timeout=120) as response:
            raw = response.read()
            result: dict[str, Any] = json.loads(raw) if raw else {}
            return result


def _dotenv() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    pairs = (line.split("=", 1) for line in ENV_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {k.strip(): v.strip().strip('"') for k, v in pairs if not k.lstrip().startswith("#")}
