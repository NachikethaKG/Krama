import io
import json
import urllib.error
import urllib.request
from typing import Self
from unittest.mock import patch

import pytest

from benchmarks.gitea import (
    GiteaResetError,
    GiteaTimeoutError,
    reset_gitea,
    reset_gitea_api,
)


class MockHTTPResponse:
    def __init__(self, status: int, data: bytes = b"") -> None:
        self.status = status
        self.data = data

    def read(self) -> bytes:
        return self.data

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass


def test_reset_gitea_api_happy_path() -> None:
    calls: list[str] = []

    def fake_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MockHTTPResponse:
        url = req.full_url
        method = req.get_method()
        calls.append(f"{method} {url}")

        if url.endswith("/api/v1/version"):
            return MockHTTPResponse(200, json.dumps({"version": "1.22.6"}).encode())
        if url.endswith("/api/v1/users/demo/repos"):
            return MockHTTPResponse(
                200,
                json.dumps([{"name": "repo-a"}, {"name": "repo-b"}]).encode(),
            )
        if "/api/v1/repos/demo/repo-" in url and method == "DELETE":
            return MockHTTPResponse(204)
        return MockHTTPResponse(404)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        deleted = reset_gitea_api(base_url="http://localhost:3001", user="demo")
        assert deleted == ["repo-a", "repo-b"]

    assert any("DELETE http://localhost:3001/api/v1/repos/demo/repo-a" in c for c in calls)
    assert any("DELETE http://localhost:3001/api/v1/repos/demo/repo-b" in c for c in calls)


def test_reset_gitea_api_specific_repo() -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MockHTTPResponse:
        url = req.full_url
        if url.endswith("/api/v1/version"):
            return MockHTTPResponse(200, b"{}")
        if url.endswith("/api/v1/repos/demo/my-repo") and req.get_method() == "DELETE":
            return MockHTTPResponse(204)
        return MockHTTPResponse(404)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        deleted = reset_gitea(base_url="http://localhost:3001", repo_name="my-repo")
        assert deleted == ["my-repo"]


def test_reset_gitea_api_timeout_raises_gitea_timeout_error() -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MockHTTPResponse:
        raise TimeoutError("The read operation timed out")

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(GiteaTimeoutError, match="timed out"),
    ):
        reset_gitea_api(base_url="http://localhost:3001")


def test_reset_gitea_api_unreachable_raises_gitea_reset_error() -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MockHTTPResponse:
        raise urllib.error.URLError("Connection refused")

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(GiteaResetError, match="Cannot reach Gitea"),
    ):
        reset_gitea_api(base_url="http://localhost:3001")


def test_reset_gitea_api_ignores_404_on_delete() -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MockHTTPResponse:
        url = req.full_url
        if url.endswith("/api/v1/version"):
            return MockHTTPResponse(200, b"{}")
        if req.get_method() == "DELETE":
            fp = io.BytesIO(b"not found")
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, fp)  # type: ignore[arg-type]
        return MockHTTPResponse(404)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        deleted = reset_gitea(repo_name="nonexistent")
        assert deleted == []


def test_reset_gitea_api_delete_error_raises() -> None:
    def fake_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MockHTTPResponse:
        url = req.full_url
        if url.endswith("/api/v1/version"):
            return MockHTTPResponse(200, b"{}")
        if req.get_method() == "DELETE":
            fp = io.BytesIO(b"internal server error")
            raise urllib.error.HTTPError(url, 500, "Server Error", {}, fp)  # type: ignore[arg-type]
        return MockHTTPResponse(404)

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        pytest.raises(GiteaResetError, match="Failed to delete repo"),
    ):
        reset_gitea(repo_name="corrupt-repo")
