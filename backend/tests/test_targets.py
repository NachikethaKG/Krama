"""The Gitea reset before a reverify (#77): which stored steps create something, and how it is deleted."""

import urllib.error
import urllib.request
from typing import Any
from unittest.mock import patch

import pytest

from app.config import Settings
from app.targets import ResetError, target_setup

pytestmark = pytest.mark.anyio

SETTINGS = Settings(gitea_url="http://localhost:3001", gitea_demo_user="demo", gitea_demo_password="pw")


def fill(name: str, value: str, url: str = "/") -> dict[str, Any]:
    return {"seq": 1, "action": {"type": "fill", "value": value}, "target": {"role": "textbox", "name": name},
            "before_state": {"url": url}}  # fmt: skip


class Answer:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self.body = body

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "Answer":
        return self

    def __exit__(self, *args: object) -> None:
        pass


def gitea(status: int, calls: list[str]) -> Any:
    def urlopen(request: urllib.request.Request, timeout: float) -> Answer:
        calls.append(
            f"{request.get_method()} {request.full_url}" + (f" {request.data!r}" if request.data else "")
        )
        if status >= 400:
            raise urllib.error.HTTPError(request.full_url, status, "x", {}, None)  # type: ignore[arg-type]
        if request.get_method() == "GET":
            return Answer(200, b'{"sha": "abc123"}')
        return Answer(status)

    return urlopen


async def reset(steps: list[dict[str, Any]], status: int = 204) -> tuple[list[str], list[str]]:
    calls: list[str] = []
    setup = target_setup("http://localhost:3001", SETTINGS)
    assert setup.reset is not None
    with patch("urllib.request.urlopen", side_effect=gitea(status, calls)):
        done = await setup.reset(steps)
    return done, calls


async def test_a_created_repository_is_deleted_over_ipv4() -> None:
    done, calls = await reset([fill("Repository Name *", "team-docs", "/repo/create")])

    assert calls == ["DELETE http://127.0.0.1:3001/api/v1/repos/demo/team-docs"]
    assert done == ["DELETE /api/v1/repos/demo/team-docs -> 204"]


async def test_a_created_branch_is_deleted_in_the_repository_it_was_made_in() -> None:
    _, calls = await reset([fill("Branch Name *", "feature-docs", "/demo/bench/branches")])

    assert calls == ["DELETE http://127.0.0.1:3001/api/v1/repos/demo/bench/branches/feature-docs"]


async def test_a_created_file_is_deleted_by_its_sha_on_its_branch() -> None:
    _, calls = await reset([fill("Name your file…", "notes.md", "/demo/bench/_new/main/")])

    assert calls[0] == "GET http://127.0.0.1:3001/api/v1/repos/demo/bench/contents/notes.md?ref=main"
    assert calls[1].startswith("DELETE http://127.0.0.1:3001/api/v1/repos/demo/bench/contents/notes.md ")
    assert '"sha": "abc123"' in calls[1] and '"branch": "main"' in calls[1]


async def test_already_gone_is_fine_and_other_steps_need_nothing() -> None:
    steps = [
        fill("Title", "Login page is blank", "/demo/r/issues/new"),  # an issue can be created twice
        {"seq": 2, "action": {"type": "click"}, "target": {"role": "button", "name": "Create Repository"}},
        fill("Repository Name", "gone"),
    ]

    done, calls = await reset(steps, status=404)

    assert len(calls) == 1 and done == ["DELETE /api/v1/repos/demo/gone -> 404"]


async def test_a_failed_delete_or_an_unknown_repository_raises() -> None:
    with pytest.raises(ResetError, match="returned 500"):
        await reset([fill("Repository Name", "r")], status=500)
    with pytest.raises(ResetError, match="repository is unknown"):
        await reset([fill("Branch Name", "b", "/")])


def test_only_gitea_has_a_reset() -> None:
    assert target_setup("https://example.com", SETTINGS).reset is None
