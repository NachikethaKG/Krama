"""The generated contract models (backend/app/contracts_gen) behave the way the backend relies on."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts_gen.common_schema import BoundingBox, ErrorResponse, ExpectedState
from app.contracts_gen.events_schema import RunEvent, RunPausedEvent, StepVerifiedEvent
from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.task_schema import Task
from app.contracts_gen.tutorial_spec_schema import Scene, TutorialSpec
from app.contracts_gen.workflow_schema import Workflow

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
TUTORIAL = FIXTURES / "tutorial-spec" / "gitea-create-repo.json"

RUN = "6f1c2a4e-1111-4b8a-9a1b-123456789abc"
TS = "2026-10-05T14:03:22Z"

GITEA_PLAN = {
    "id": RUN,
    "task_id": RUN,
    "revision": 1,
    "status": "proposed",
    "risk": "low",
    "expected_result": "The new repository's page is shown",
    "created_at": TS,
    "steps": [
        {
            "seq": 1,
            "action": {"type": "click"},
            "target": {"role": "menu", "name": "Create…"},
            "instruction_text": "Open the + menu at the top right.",
            "expected_state": {
                "url_matches": "^/$",
                "visible": [{"role": "menuitem", "name": "New Repository"}],
            },
            "risk": "low",
        },
        {
            "seq": 2,
            "action": {"type": "fill", "value": "demo-repo"},
            "target": {"role": "textbox", "name": "Repository Name"},
            "instruction_text": "Type the repository name.",
            "expected_state": {
                "field_values": [{"role": "textbox", "name": "Repository Name", "value": "demo-repo"}]
            },
            "risk": "low",
        },
    ],
}

events: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)


def test_gitea_plan_parses_and_enums_are_plain_strings() -> None:
    plan = Plan.model_validate(GITEA_PLAN)

    assert plan.risk == "low"  # type alias, not a RootModel wrapper (contracts/README.md)
    assert plan.steps[1].action.type == "fill"
    assert plan.steps[0].target.name == "Create…"


def test_events_parse_into_the_matching_class() -> None:
    verified = events.validate_python(
        {
            "type": "step.verified",
            "run_id": RUN,
            "seq": 4,
            "ts": TS,
            "step_seq": 2,
            "method": ["url"],
            "confidence": 1,
        }
    )
    paused = events.validate_python(
        {"type": "run.paused", "run_id": RUN, "seq": 5, "ts": TS, "reason": "captcha", "step_seq": 3}
    )

    assert isinstance(verified, StepVerifiedEvent)
    assert isinstance(paused, RunPausedEvent)
    assert paused.reason == "captcha"


@pytest.mark.parametrize(
    "bad",
    [
        {"type": "heartbeat", "run_id": RUN, "seq": 1, "ts": TS},  # keep-alives are SSE comments, not events
        {
            "type": "step.verified",
            "run_id": RUN,
            "seq": 4,
            "ts": TS,
            "step_seq": 2,
            "method": [],
            "confidence": 0.5,
        },
        {
            "type": "step.verified",
            "run_id": RUN,
            "seq": 4,
            "ts": TS,
            "step_seq": 2,
            "method": ["url"],
            "confidence": 2,
        },
        {"type": "run.paused", "run_id": RUN, "seq": 5, "ts": TS, "step_seq": 3},  # missing reason
    ],
)
def test_invalid_events_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        events.validate_python(bad)


def test_timestamps_must_have_a_timezone() -> None:
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "id": RUN,
                "prompt": "x",
                "target_url": "http://localhost:3001",
                "status": "planning",
                "created_at": "2026-10-05T14:03:22",
            }  # no Z: naive datetimes are rejected
        )
    task = Task.model_validate(
        {
            "id": RUN,
            "prompt": "x",
            "target_url": "http://localhost:3001",
            "status": "planning",
            "created_at": TS,
        }
    )
    assert isinstance(task.created_at, datetime)
    assert task.created_at.tzinfo is not None


def test_closed_objects_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Plan.model_validate({**GITEA_PLAN, "surprise": 1})


def test_bounding_box_needs_exactly_four_numbers() -> None:
    assert TypeAdapter(BoundingBox).validate_python([10, 20, 30, 40]) == (10, 20, 30, 40)
    with pytest.raises(ValidationError):
        TypeAdapter(BoundingBox).validate_python([1, 2, 3])


def test_error_response_shape() -> None:
    body = ErrorResponse.model_validate(
        {"error": {"code": "plan_not_editable", "message": "Plan is approved"}}
    )
    assert body.error.code == "plan_not_editable"


def test_empty_expected_state_is_not_rejected_by_pydantic() -> None:
    """Known limit (contracts/README.md): minProperties isn't generated. Planner/verifier must check it."""
    assert ExpectedState.model_validate({}).model_dump(exclude_none=True) == {}


def test_workflow_fixture_steps_carry_their_scroll() -> None:
    workflow = Workflow.model_validate_json((FIXTURES / "gitea-create-repo-workflow.json").read_bytes())

    checkbox = workflow.steps[3].target
    assert checkbox.bbox is not None and checkbox.scroll is not None and workflow.viewport is not None
    assert checkbox.bbox[1] > workflow.viewport.height  # below the fold on the page...
    on_screen_y = checkbox.bbox[1] - checkbox.scroll.y
    assert 0 <= on_screen_y < workflow.viewport.height  # ...but on screen at the click


def test_tutorial_spec_fixture_matches_its_workflow() -> None:
    spec = TutorialSpec.model_validate_json(TUTORIAL.read_bytes())
    workflow = Workflow.model_validate_json((FIXTURES / "gitea-create-repo-workflow.json").read_bytes())

    assert spec.workflow_id == workflow.id
    assert [s.step_seq for s in spec.scenes] == [s.seq for s in workflow.steps]
    assert [s.caption.text for s in spec.scenes] == [s.instruction_text for s in workflow.steps]
    last = spec.scenes[-1]
    assert spec.total_duration_ms == last.start_ms + last.duration_ms
    for scene, step in zip(spec.scenes, workflow.steps, strict=True):
        assert scene.highlight is not None and scene.highlight.bbox == step.target.bbox
        assert scene.scroll == step.target.scroll


def test_scene_without_an_element_needs_no_cursor_or_highlight() -> None:
    scene = Scene.model_validate(
        {
            "id": "scene-1",
            "step_seq": 1,
            "start_ms": 0,
            "duration_ms": 900,
            "action": {"type": "navigate", "value": "/demo/demo-repo/branches"},
            "caption": {"text": "Go to the **Branches** page."},
            "recording": {"start_ms": 0, "end_ms": 650},
        }
    )

    assert scene.cursor is None and scene.highlight is None and scene.camera is None
    assert scene.caption.words is None  # Web Speech gives word timings only at playback


@pytest.mark.parametrize(
    "change",
    [
        {"step_index": 1},  # #70's draft name; the contract uses step_seq
        {"cursor": {"path": [{"x": 0, "y": 0}], "start_ms": 0, "end_ms": 1, "click_type": "single"}},
        {"scroll": {"x": 0, "y": -1}},
    ],
)
def test_invalid_scenes_are_rejected(change: dict[str, object]) -> None:
    spec = json.loads(TUTORIAL.read_text(encoding="utf-8"))
    spec["scenes"][0] |= change

    with pytest.raises(ValidationError):
        TutorialSpec.model_validate(spec)
