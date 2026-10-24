"""GET /metrics/summary (#102): serves the benchmark's summary.json, checked against the contract."""

import json
from pathlib import Path

import pytest

from app.api import metrics
from app.config import Settings
from tests.api.test_flow import Api, Sessions, services

pytestmark = pytest.mark.anyio

SUMMARY = {
    "generated_at": "2026-10-24T12:00:00Z",
    "total_tasks": 1,
    "overall_success_rate": 0.8,
    "overall_verifier_accuracy": 1.0,
    "tasks": [
        {
            "task_name": "gitea-create-repo",
            "total_runs": 5,
            "successful_runs": 4,
            "success_rate": 0.8,
            "verifier_accuracy": 1.0,
            "false_alarm_rate": 0.0,
            "avg_latency_ms": 41000.0,
            "p90_latency_ms": 52000.0,
        }
    ],
}


@pytest.fixture
def summary_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "summary.json"
    monkeypatch.setattr(metrics, "get_settings", lambda: Settings(metrics_summary_path=path))
    return path


def write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


async def test_serves_the_benchmark_summary(sessions: Sessions, tmp_path: Path, summary_file: Path) -> None:
    write(summary_file, SUMMARY)
    async with Api(services(sessions, tmp_path)) as api:
        response = await api.client.get("/metrics/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["overall_success_rate"] == 0.8 and body["tasks"][0]["task_name"] == "gitea-create-repo"
    assert body["tasks"][0]["failed_runs"] == 0  # contract defaults filled in


async def test_no_benchmark_yet_is_a_404(sessions: Sessions, tmp_path: Path, summary_file: Path) -> None:
    async with Api(services(sessions, tmp_path)) as api:
        response = await api.client.get("/metrics/summary")

    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"


async def test_a_summary_that_breaks_the_contract_is_not_served(
    sessions: Sessions, tmp_path: Path, summary_file: Path
) -> None:
    write(summary_file, {**SUMMARY, "overall_success_rate": 1.7})
    async with Api(services(sessions, tmp_path)) as api:
        response = await api.client.get("/metrics/summary")

    assert response.status_code == 500 and response.json()["error"]["code"] == "internal"


async def test_signed_out_gets_401(sessions: Sessions, tmp_path: Path, summary_file: Path) -> None:
    write(summary_file, SUMMARY)
    async with Api(services(sessions, tmp_path)) as api:
        api.client.cookies.clear()
        response = await api.client.get("/metrics/summary")

    assert response.status_code == 401
