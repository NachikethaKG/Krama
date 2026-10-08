import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from app.contracts_gen.common_schema import Risk
from app.contracts_gen.plan_schema import Plan, PlannedStep
from app.runs.approval import console_approver, format_plan

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def planned(seq: int, risk: str, action: dict[str, Any], target: dict[str, Any]) -> PlannedStep:
    return PlannedStep.model_validate(
        {
            "seq": seq,
            "action": action,
            "target": target,
            "instruction_text": f"Step {seq}.",
            "expected_state": {"url_matches": "^/$"},
            "risk": risk,
        }
    )


def plan(*risks: Risk, fill: tuple[str, str] | None = None) -> Plan:
    steps = [
        planned(i, r, {"type": "click"}, {"role": "button", "name": f"B{i}"}) for i, r in enumerate(risks, 1)
    ]
    if fill:
        name, value = fill
        steps.append(
            planned(
                len(steps) + 1, "low", {"type": "fill", "value": value}, {"role": "textbox", "name": name}
            )
        )
    worst: Risk = "high" if "high" in risks else "medium" if "medium" in risks else "low"
    return Plan(
        id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        revision=1,
        status="proposed",
        risk=worst,
        expected_result="done",
        steps=steps,
        created_at=datetime.now(UTC),
    )


def answers(*replies: str) -> tuple[list[str], Any]:
    asked: list[str] = []
    queue = list(replies)

    def ask(prompt: str) -> str:
        asked.append(prompt)
        return queue.pop(0)

    return asked, ask


async def test_yes_flag_approves_low_and_medium_plans_without_asking() -> None:
    asked, ask = answers()

    assert await console_approver(auto_approve=True, ask=ask, show=lambda _: None)(plan("low", "medium"))
    assert asked == []


async def test_high_risk_always_needs_a_typed_yes_even_with_the_flag() -> None:
    asked, ask = answers("y")

    approved = await console_approver(auto_approve=True, ask=ask, show=lambda _: None)(plan("low", "high"))

    assert not approved  # "y" is not enough for a high-risk step
    assert "HIGH risk" in asked[0] and "[2]" in asked[0]


async def test_high_risk_runs_after_typed_yes() -> None:
    _, ask = answers("yes")

    assert await console_approver(auto_approve=False, ask=ask, show=lambda _: None)(plan("high"))


@pytest.mark.parametrize(("reply", "expected"), [("y", True), ("YES", True), ("", False), ("n", False)])
async def test_interactive_approval(reply: str, expected: bool) -> None:
    _, ask = answers(reply)

    assert await console_approver(auto_approve=False, ask=ask, show=lambda _: None)(plan("low")) is expected


def test_plan_printout_masks_password_values() -> None:
    text = format_plan(plan("low", fill=("Password *", "hunter2")))

    assert "hunter2" not in text
    assert "'***'" in text
