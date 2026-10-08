from pathlib import Path

import pytest

from app import cli
from app.config import Settings
from app.llm import FakeProvider, FakeResponse
from tests.runs.test_runner import GOOD_PLAN, TASK


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    settings = Settings(llm_provider="fake", artifacts_dir=tmp_path)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    reply = FakeResponse(name="plan", schema_name="LLMPlan", response=GOOD_PLAN)
    monkeypatch.setattr(cli, "create_provider", lambda _: FakeProvider([reply]))
    return settings


def test_help_lists_the_run_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["--help"])

    assert "run" in capsys.readouterr().out


def test_login_needs_a_known_site() -> None:
    with pytest.raises(SystemExit):
        cli.main(["run", "x", "--target", "http://localhost:1", "--login"])


def test_run_prints_each_step_and_writes_the_run_log(
    site: str, local_settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(["run", TASK, "--target", site, "--yes"])

    out = capsys.readouterr().out
    assert code == 0, out
    assert "Plan (4 steps, risk low)" in out
    assert out.count("  ok ") == 4
    assert "VERIFIED: every step verified" in out
    logs = list((local_settings.artifacts_dir / "runs").glob("*/run-log.json"))
    assert len(logs) == 1


def test_rejected_plan_exits_non_zero(
    site: str, local_settings: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    code = cli.main(["run", TASK, "--target", site])

    assert code == 1
    assert "REJECTED" in capsys.readouterr().out
