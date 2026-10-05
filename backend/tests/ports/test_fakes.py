from datetime import UTC, datetime
from typing import cast

import pytest
from playwright.async_api import Page
from pydantic import ValidationError

from app.ports import ObservedState, PageState, PlanDraft, PolicyDecision, StepRef
from app.ports.fakes import FakeObserver, FakePolicy
from app.ports.models import Action, RiskReport, StepRisk, Target

pytestmark = pytest.mark.anyio

PAGE = cast(Page, object())  # fakes never touch the page


def step(seq: int, action: str = "click", name: str = "New Repository") -> StepRef:
    return StepRef.model_validate(
        {
            "seq": seq,
            "action": {"type": action},
            "target": {"role": "button", "name": name},
            "instruction_text": f"Step {seq}",
        }
    )


def observed(url: str) -> ObservedState:
    return ObservedState(url=url, title="t", captured_at=datetime.now(UTC))


async def test_fake_observer_returns_scripted_states_in_order() -> None:
    obs = FakeObserver([observed("/repo/create"), observed("/demo/demo-repo")])

    first = await obs.capture(PAGE, step(1))
    second = await obs.capture(PAGE, step(2))
    fallback = await obs.capture(PAGE, step(3))

    assert [first.url, second.url, fallback.url] == ["/repo/create", "/demo/demo-repo", "/"]
    assert [s.seq for s in obs.captured] == [1, 2, 3]


async def test_fake_observer_recording_lifecycle() -> None:
    obs = FakeObserver()
    await obs.start_recording(PAGE)
    await obs.capture(PAGE, step(1))

    ref = await obs.stop_recording()

    assert ref.event_count == 1
    assert ref.ended_at >= ref.started_at
    assert obs.recording is False


async def test_fake_observer_stop_without_start_raises() -> None:
    with pytest.raises(RuntimeError):
        await FakeObserver().stop_recording()


async def test_fake_policy_allows_by_default_and_uses_scripted_decisions() -> None:
    pause = PolicyDecision(verdict="pause", reason="destructive_action", message="Deletes a repository")
    policy = FakePolicy(decisions={2: pause})
    page = PageState(url="/repo/create", title="New Repository")

    assert (await policy.check_action(step(1), page)).verdict == "allow"
    assert await policy.check_action(step(2), page) == pause
    assert len(policy.checked) == 2


async def test_fake_policy_plan_risk_is_the_highest_step_risk() -> None:
    policy = FakePolicy(risks={2: "high"})
    plan = PlanDraft(task="Create a repository", steps=[step(1), step(2), step(3)])

    report = await policy.assess_plan(plan)

    assert report.level == "high"
    assert [s.risk for s in report.steps] == ["low", "high", "low"]


def test_risk_report_of_empty_plan_is_low() -> None:
    assert RiskReport.from_steps([]).level == "low"
    assert RiskReport.from_steps([StepRisk(seq=1, risk="medium", reason="x")]).level == "medium"


def test_fake_policy_mask_is_identity_and_recorded() -> None:
    policy = FakePolicy()
    state = observed("/user/login")

    assert policy.mask(state) is state
    assert policy.masked == [state]


@pytest.mark.parametrize(
    "bad",
    [
        {"seq": 0, "action": {"type": "click"}, "target": {}, "instruction_text": "x"},  # seq starts at 1
        {"seq": 1, "action": {"type": "hover"}, "target": {}, "instruction_text": "x"},  # unknown action
        {"seq": 1, "action": {"type": "click"}, "target": {}, "instruction_text": ""},  # empty text
        {"seq": 1, "action": {"type": "click"}, "target": {}, "instruction_text": "x", "extra": 1},
    ],
)
def test_step_ref_rejects_invalid_data(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        StepRef.model_validate(bad)


def test_models_are_immutable() -> None:
    with pytest.raises(ValidationError):
        Action(type="click").type = "fill"  # type: ignore[misc]


def test_policy_decision_rejects_unknown_verdict() -> None:
    with pytest.raises(ValidationError):
        PolicyDecision.model_validate({"verdict": "maybe"})


def test_target_fields_are_all_optional() -> None:
    assert Target() == Target(role=None, name=None, selector=None)
