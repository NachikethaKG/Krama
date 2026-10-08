import pytest
from pydantic import ValidationError

from app.contracts_gen import common_schema
from app.contracts_gen.plan_schema import PlannedStep
from app.ports.models import Action, StepRef, Target


def test_port_action_and_target_are_the_contract_types() -> None:
    assert Action is common_schema.Action
    assert Target is common_schema.Target


def test_a_planned_step_crosses_the_port_without_conversion() -> None:
    planned = PlannedStep(
        seq=1,
        action=common_schema.Action(type="click"),
        target=common_schema.Target(role="link", name="New Repository"),
        instruction_text="Click New Repository.",
        expected_state=common_schema.ExpectedState(url_matches="^/repo/create$"),
        risk="low",
    )

    ref = StepRef(
        seq=planned.seq,
        action=planned.action,
        target=planned.target,
        instruction_text=planned.instruction_text,
    )

    assert ref.action is planned.action
    assert ref.target.name == "New Repository"


def test_step_ref_still_rejects_unknown_action_types() -> None:
    with pytest.raises(ValidationError):
        StepRef.model_validate(
            {
                "seq": 1,
                "action": {"type": "hover"},
                "target": {},
                "instruction_text": "Hover",
            }
        )
