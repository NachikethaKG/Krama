"""The generated contract models (backend/app/contracts_gen) behave the way the backend relies on."""

from datetime import datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.contracts_gen.common_schema import BoundingBox, ErrorResponse, ExpectedState
from app.contracts_gen.events_schema import RunEvent, RunPausedEvent, StepVerifiedEvent
from app.contracts_gen.plan_schema import Plan
from app.contracts_gen.task_schema import Task

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
