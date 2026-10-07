import json
from pathlib import Path

import pytest

from app.agent import ActionExecutor
from app.agent.runlog import MASK, RunLog, ScriptedStep, is_sensitive, run_script
from app.contracts_gen.common_schema import Action, Target

pytestmark = pytest.mark.anyio

FORM_STEPS = [
    ScriptedStep(action=Action(type="navigate", value="/form"), section="precondition"),
    ScriptedStep(
        action=Action(type="fill", value="demo-repo"), target=Target(role="textbox", name="Repository")
    ),
    ScriptedStep(
        action=Action(type="press", value="Enter"), target=Target(role="textbox", name="Repository")
    ),
    ScriptedStep(action=Action(type="wait"), target=Target(role="heading", name="Done")),
]


async def test_run_script_logs_every_action(executor: ActionExecutor) -> None:
    log = await run_script(executor, FORM_STEPS, task="submit the form", base_url="http://krama.test")

    assert log.ok
    assert [e.seq for e in log.entries] == [1, 2, 3, 4]
    assert [e.section for e in log.entries] == ["precondition", "step", "step", "step"]
    assert log.entries[-1].result.url_after == "/done"
    assert log.duration_ms is not None and log.duration_ms >= 0
    assert log.finished_at is not None and log.finished_at >= log.started_at


async def test_run_script_stops_at_first_failure(executor: ActionExecutor) -> None:
    steps = [
        ScriptedStep(action=Action(type="click"), target=Target(role="button", name="No such button")),
        ScriptedStep(action=Action(type="navigate", value="/form")),
    ]

    log = await run_script(executor, steps, task="t", base_url="http://krama.test")

    assert not log.ok
    assert len(log.entries) == 1
    assert log.failed_entry is not None
    assert log.failed_entry.result.error is not None
    assert log.failed_entry.result.error.code == "target_not_found"


async def test_sensitive_values_are_masked_in_the_log(executor: ActionExecutor, tmp_path: Path) -> None:
    secret = "hunter2-very-secret"
    steps = [
        ScriptedStep(action=Action(type="navigate", value="/form")),
        ScriptedStep(
            action=Action(type="fill", value=secret),
            target=Target(role="textbox", name="Repository"),
            sensitive=True,
        ),
    ]

    log = await run_script(executor, steps, task="t", base_url="http://krama.test")
    path = log.write(tmp_path)

    assert log.ok
    assert log.entries[1].action.value == MASK
    assert secret not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["Password", "Password *", "API key", "Access Token", "Card number"])
def test_password_like_field_names_are_sensitive(name: str) -> None:
    step = ScriptedStep(action=Action(type="fill", value="x"), target=Target(role="textbox", name=name))

    assert is_sensitive(step)


@pytest.mark.parametrize("name", ["Repository Name", "Username or Email Address", "Description"])
def test_ordinary_field_names_are_not_sensitive(name: str) -> None:
    step = ScriptedStep(action=Action(type="fill", value="x"), target=Target(role="textbox", name=name))

    assert not is_sensitive(step)


async def test_run_log_is_written_as_json_and_reads_back(executor: ActionExecutor, tmp_path: Path) -> None:
    log = await run_script(executor, FORM_STEPS, task="submit the form", base_url="http://krama.test")

    path = log.write(tmp_path)

    assert path == tmp_path / "runs" / str(log.run_id) / "run-log.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert RunLog.model_validate(data) == log
