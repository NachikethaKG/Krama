from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_unknown_route_is_404() -> None:
    client = TestClient(create_app())

    assert client.get("/api/v1/does-not-exist").status_code == 404


def test_cors_allows_frontend_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
