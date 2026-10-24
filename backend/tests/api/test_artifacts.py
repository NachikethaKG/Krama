import os
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent import PlaywrightSession, SessionConfig
from app.api import artifacts
from app.api.auth import current_user
from app.api.services import get_services
from app.db import UserRow
from app.main import create_app
from app.storage import LocalFsStore, get_artifact_store

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store(tmp_path: Path) -> LocalFsStore:
    root = tmp_path / "artifacts"
    (root / "runs" / "r1").mkdir(parents=True)
    (root / "runs" / "r1" / "1-after.png").write_bytes(PNG)
    (root / "runs" / "r1" / "recording.json").write_bytes(b'{"events": []}')
    (tmp_path / "secret.json").write_bytes(b'{"token": "not-for-you"}')
    return LocalFsStore(root)


def signed_in_app(store: LocalFsStore, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Headers and path safety only: sign-in and ownership are stubbed here and tested end to end in
    tests/api/test_auth.py."""
    app = create_app()
    app.dependency_overrides[get_artifact_store] = lambda: store
    app.dependency_overrides[current_user] = lambda: UserRow(email="a@b.test", password_hash="x")
    app.dependency_overrides[get_services] = lambda: None  # no lifespan here; _owns is stubbed below

    async def owns(key: str, *_: object) -> bool:
        return key.startswith("runs/")

    monkeypatch.setattr(artifacts, "_owns", owns)
    return app


@pytest.fixture
def client(store: LocalFsStore, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    yield TestClient(signed_in_app(store, monkeypatch))


def test_serves_a_screenshot_with_safe_headers(client: TestClient) -> None:
    response = client.get("/api/v1/artifacts/runs/r1/1-after.png")

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_serves_json(client: TestClient) -> None:
    response = client.get("/api/v1/artifacts/runs/r1/recording.json")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"events": []}


@pytest.mark.parametrize(
    "path",
    [
        "runs/r1/missing.png",
        "runs/r1",
        "..%2Fsecret.json",
        "%2e%2e/secret.json",
        "runs/r1/..%2F..%2F..%2Fsecret.json",
        "runs%5C..%5C..%5Csecret.json",
        "%2Fetc%2Fpasswd",
        "runs/r1/1-after.png%00.html",
    ],
)
def test_missing_or_unsafe_paths_are_a_plain_404(client: TestClient, path: str) -> None:
    response = client.get(f"/api/v1/artifacts/{path}")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "Artifact not found"}}
    assert b"not-for-you" not in response.content


def test_artifacts_are_read_only(client: TestClient) -> None:
    for method in ("put", "post", "delete"):
        response = client.request(method, "/api/v1/artifacts/runs/r1/1-after.png", headers={"X-Krama": "1"})
        assert response.status_code == 405


GITEA = os.environ.get("GITEA_URL", "http://localhost:3001")


def _gitea_up() -> bool:
    try:
        with urllib.request.urlopen(f"{GITEA}/api/healthz", timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.anyio
@pytest.mark.skipif(not _gitea_up(), reason=f"Gitea not reachable at {GITEA}; start it with `just up`")
async def test_real_screenshot_round_trips_through_store_and_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = LocalFsStore(tmp_path)
    async with PlaywrightSession(SessionConfig(base_url=GITEA)) as session:
        await session.page.goto(f"{GITEA}/explore/repos")
        shot = await session.page.screenshot()
    await store.put("runs/live/explore.png", shot, "image/png")
    app = signed_in_app(store, monkeypatch)

    response = TestClient(app).get("/api/v1/artifacts/runs/live/explore.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == shot and len(shot) > 10_000
