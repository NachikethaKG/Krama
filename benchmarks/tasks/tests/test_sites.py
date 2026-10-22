"""GitHub tasks (#89): setup and grading go to the task's api_base with the test account's token.

Run: cd backend && uv run pytest ../benchmarks/tasks/tests -o addopts=""
"""

from __future__ import annotations

import io
import urllib.request
from typing import Any

import pytest

from benchmarks.tasks import runner
from benchmarks.tasks.runner import Credentials, TaskSetupError, check_success, run_setup
from benchmarks.tasks.schema import load_all_tasks, load_task_from_yaml

GITHUB = Credentials(user="krama-bot", token="t0ken", org="krama-bench")
TASK = load_task_from_yaml(
    """
name: github-create-label
prompt: "Create the label."
target: "https://github.com"
site: github
api_base: "https://api.github.com"
setup:
  api_calls:
    - { method: POST, url: "/orgs/{org}/repos", body: { name: "{org}-x" }, ok_status: [201] }
success_check:
  type: api
  assertion:
    method: GET
    url: "/repos/{org}/bench-labels/labels/needs-docs"
    accept: "application/vnd.github.raw+json"
    body_contains: ["d73a4a", "Docs are missing"]
"""
)


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        pass


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[urllib.request.Request]:
    requests: list[urllib.request.Request] = []

    def urlopen(req: urllib.request.Request, timeout: float) -> FakeResponse:
        requests.append(req)
        response = FakeResponse(b'{"color": "d73a4a", "description": "Docs are missing"}')
        response.status = 201 if req.get_method() == "POST" else 200
        return response

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return requests


def test_setup_goes_to_the_api_base_with_the_token(sent: list[urllib.request.Request]) -> None:
    run_setup(TASK, GITHUB)

    [req] = sent
    assert req.full_url == "https://api.github.com/orgs/krama-bench/repos"
    assert req.get_header("Authorization") == "Bearer t0ken"
    assert req.data == b'{"name": "krama-bench-x"}'  # placeholders inside the body are filled too


def test_check_needs_every_listed_string_and_sends_accept(sent: list[urllib.request.Request]) -> None:
    result = check_success(TASK, GITHUB)

    assert result.passed, result.detail
    assert sent[0].full_url == "https://api.github.com/repos/krama-bench/bench-labels/labels/needs-docs"
    assert sent[0].get_header("Accept") == "application/vnd.github.raw+json"


def test_check_fails_when_one_listed_string_is_missing(sent: list[urllib.request.Request]) -> None:
    data: dict[str, Any] = TASK.success_check.model_dump()
    data["assertion"]["body_contains"] = ["d73a4a", "Docs are complete"]
    task = TASK.model_copy(update={"success_check": TASK.success_check.model_validate(data)})

    result = check_success(task, GITHUB)

    assert not result.passed and "Docs are complete" in result.detail


def test_gitea_tasks_still_use_basic_auth_on_the_target(sent: list[urllib.request.Request]) -> None:
    gitea = next(t for t in load_all_tasks() if t.name == "gitea-create-branch")

    check_success(gitea, Credentials(user="demo", password="pw"))

    assert sent[0].full_url.startswith("http://127.0.0.1:3001/api/v1/repos/demo/")
    assert sent[0].get_header("Authorization", "").startswith("Basic ")


def test_a_github_task_without_a_token_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "_dotenv", dict)
    monkeypatch.delenv("GITHUB_BENCH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TEST_ORG", raising=False)

    with pytest.raises(TaskSetupError):
        Credentials.for_task(TASK)


def test_every_task_file_loads_and_github_tasks_name_their_api() -> None:
    tasks = load_all_tasks()
    github = [t for t in tasks if t.site == "github"]

    assert len(tasks) == 12 and len(github) == 6
    assert all(t.api_base == "https://api.github.com" for t in github)
    assert all(isinstance(a := t.success_check.assertion, dict) and "{org}" in a["url"] for t in github)
