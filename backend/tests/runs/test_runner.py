"""`run_task` end to end: real browser, real observer (screenshots + rrweb), real verifier, fake LLM."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.agent.runlog import ScriptedStep
from app.contracts_gen.common_schema import Action, Target
from app.llm import FakeProvider, FakeResponse
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.runs import RunOptions, RunParts, RunReport, run_task
from app.verifier import RuleVerifier

pytestmark = pytest.mark.anyio

TASK = "Create an item called demo-item with a README"


def step(seq: int, action: Any, target: Any, text: str, expected: Any) -> dict[str, Any]:
    return {
        "seq": seq,
        "action": action,
        "target": target,
        "instruction_text": text,
        "expected_state": expected,
        "risk": "low",
    }


ITEM_NAME = {"role": "textbox", "name": "Item name"}
README_BOX = {"role": "checkbox", "name": "Add a README"}
GOOD_PLAN: dict[str, Any] = {
    "expected_result": "The item demo-item exists.",
    "steps": [
        step(
            1,
            {"type": "click"},
            {"role": "link", "name": "New item"},
            "Click New item.",
            {"url_matches": "^/form$", "visible": [ITEM_NAME]},
        ),
        step(
            2,
            {"type": "fill", "value": "demo-item"},
            ITEM_NAME,
            "Type the name.",
            {"field_values": [{**ITEM_NAME, "value": "demo-item"}]},
        ),
        step(3, {"type": "click"}, README_BOX, "Tick Add a README.", {"checked": [README_BOX]}),
        step(
            4,
            {"type": "click"},
            {"role": "button", "name": "Create item"},
            "Click Create item.",
            {"url_matches": "^/done$", "visible": [{"role": "heading", "name": "Item created"}]},
        ),
    ],
}


def artifacts_exist(report: RunReport, tmp_path: Path) -> bool:
    shots = [s.observed.screenshot_path for s in report.steps if s.observed]
    recording = report.run_dir(tmp_path) / "recording.json"
    return (
        recording.exists() and len(shots) == len(report.steps) and all(p and Path(p).exists() for p in shots)
    )


def plan_with(**changes: Any) -> dict[str, Any]:
    plan: dict[str, Any] = json.loads(json.dumps(GOOD_PLAN))
    for index, patch in changes.items():
        plan["steps"][int(index.removeprefix("s")) - 1].update(patch)
    return plan


def parts(reply: dict[str, Any], *, approve: bool = True) -> RunParts:
    async def approver(_: Any) -> bool:
        return approve

    llm = FakeProvider([FakeResponse(name="plan", schema_name="LLMPlan", response=reply)])
    return RunParts(
        planner=LLMPlanner(llm, max_attempts=1),
        verifier=RuleVerifier(),
        observer_for=lambda run_dir: PageObserver(artifacts_dir=run_dir),
        approve=approver,
    )


async def run(site: str, tmp_path: Path, reply: dict[str, Any], **kw: Any) -> RunReport:
    approve = kw.pop("approve", True)
    options = RunOptions(task=TASK, target_url=site, verify_timeout_s=kw.pop("verify_timeout_s", 3.0), **kw)
    return await run_task(options, parts(reply, approve=approve), artifacts_dir=tmp_path)


async def test_planned_run_executes_observes_and_verifies(site: str, tmp_path: Path) -> None:
    lines: list[str] = []

    report = await run(site, tmp_path, GOOD_PLAN, on_event=lines.append)

    assert report.status == "verified", report.message
    assert [s.seq for s in report.steps] == [1, 2, 3, 4]
    assert all(s.verification and s.verification.verified for s in report.steps)
    assert report.steps[-1].observed is not None and report.steps[-1].observed.url == "/done"
    assert report.plan is not None and report.planner_model == "fake"
    # the observer's artifacts (screenshots, rrweb recording) land in the run's folder
    assert report.recording is not None and report.recording.event_count > 0
    assert artifacts_exist(report, tmp_path)
    # the log is written and reads back
    path = report.write(tmp_path)
    assert RunReport.model_validate_json(path.read_text(encoding="utf-8")).status == "verified"
    assert sum(line.lstrip().startswith("ok") for line in lines) == 4


async def test_rejected_plan_runs_nothing(site: str, tmp_path: Path) -> None:
    report = await run(site, tmp_path, GOOD_PLAN, approve=False)

    assert report.status == "rejected"
    assert report.steps == [] and report.recording is None


async def test_failed_action_stops_the_run(site: str, tmp_path: Path) -> None:
    reply = plan_with(s2={"target": {"role": "textbox", "name": "No such field"}})

    report = await run(site, tmp_path, reply, session=None)

    assert report.status == "failed"
    assert len(report.steps) == 2
    assert report.steps[1].result.error is not None
    assert report.steps[1].result.error.code == "target_not_found"
    assert report.recording is not None  # recording is stopped and saved even on failure


async def test_unmet_expected_state_fails_after_retrying(site: str, tmp_path: Path) -> None:
    reply = plan_with(s1={"expected_state": {"url_matches": "^/wrong-page$"}})

    report = await run(site, tmp_path, reply, verify_timeout_s=0.6)

    assert report.status == "failed"
    first = report.steps[0]
    assert first.result.ok and first.verification is not None
    assert first.verification.verification.result == "failed"
    assert first.verify_attempts > 1


async def test_verification_waits_for_a_late_navigation(site: str, tmp_path: Path) -> None:
    reply = {
        "expected_result": "Done page shown.",
        "steps": [step(1, {"type": "click"}, {"role": "link", "name": "Slow page"}, "Open the slow page.",
                       {"url_matches": "^/done$"})],
    }  # fmt: skip

    report = await run(site, tmp_path, reply)

    assert report.status == "verified", report.message
    assert report.steps[0].verify_attempts > 1


async def test_needs_clarification_is_reported(site: str, tmp_path: Path) -> None:
    reply = {"expected_result": "", "steps": [], "clarification_question": "What should the item be called?"}

    report = await run(site, tmp_path, reply)

    assert report.status == "needs_clarification"
    assert report.message == "What should the item be called?"


async def test_failed_precondition_stops_before_planning(site: str, tmp_path: Path) -> None:
    setup = [ScriptedStep(action=Action(type="click"), target=Target(role="button", name="Sign In"))]

    report = await run(site, tmp_path, GOOD_PLAN, preconditions=setup, verify_timeout_s=0.5)

    assert report.status == "error"
    assert report.plan is None
    assert "precondition failed" in report.message


async def test_password_values_are_masked_in_the_run_log(site: str, tmp_path: Path) -> None:
    secret = "s3cret-pw-value"
    reply = plan_with(s3={
        "action": {"type": "fill", "value": secret},
        "target": {"role": "textbox", "name": "Password"},
        "expected_state": {"url_matches": "^/form$"},
    })  # fmt: skip

    report = await run(site, tmp_path, reply)
    text = report.write(tmp_path).read_text(encoding="utf-8")

    assert report.status == "verified", report.message
    assert report.steps[2].action.value == "***"
    assert secret not in text
    assert secret not in (report.run_dir(tmp_path) / "recording.json").read_text(encoding="utf-8")
