"""Outline planner (#467) and step decider (#468), with the fake LLM."""

from uuid import uuid4

import pytest

from app.contracts_gen.plan_schema import OutlineItem
from app.llm import FakeProvider, FakeResponse
from app.planner.planner import NeedsClarificationError, PlanRequest
from app.planner.stepwise import (
    DECIDE_SYSTEM,
    DecidedTarget,
    LLMDecision,
    OutlinePlanner,
    StepContext,
    StepDecider,
    normalize,
    to_step,
)

pytestmark = pytest.mark.anyio

OSM_PAGE = '- banner:\n  - textbox "Search"\n  - button "Go"\n- main:\n  - heading "OpenStreetMap"'


def outline_reply(**overrides: object) -> FakeResponse:
    response = {
        "expected_result": "The map shows Bengaluru.",
        "title": "Search the map for a place",
        "outline": ["Search for the place", "Open the first result", "  "],
        "risk": "low",
        "clarification_question": None,
    } | overrides
    return FakeResponse(name="outline", schema_name="LLMOutline", response=response)


async def test_the_outline_is_a_step_mode_plan_without_steps() -> None:
    llm = FakeProvider([outline_reply()])
    request = PlanRequest(task_id=uuid4(), task="Search the map for Bengaluru", page_snapshot=OSM_PAGE)

    result = await OutlinePlanner(llm).plan(request)

    plan = result.plan
    assert plan.mode == "steps" and plan.steps == []
    assert plan.outline == [
        OutlineItem(seq=1, text="Search for the place"),
        OutlineItem(seq=2, text="Open the first result"),
    ]
    assert plan.title == "Search the map for a place" and plan.risk == "low"
    # The page goes in as untrusted data, never into the system prompt.
    system, prompt, _ = llm.calls[0]
    assert "textbox" not in system and '<page_snapshot untrusted="true">' in prompt


async def test_an_unclear_task_asks_a_question() -> None:
    llm = FakeProvider([outline_reply(outline=[], clarification_question="Which todo list?")])
    request = PlanRequest(task_id=uuid4(), task="Add a todo")

    with pytest.raises(NeedsClarificationError, match="Which todo list"):
        await OutlinePlanner(llm).plan(request)


async def test_the_decider_returns_one_step_with_an_empty_expected_state() -> None:
    decision = {
        "thought": "The search box is empty.",
        "outline_seq": 1,
        "action": "fill",
        "target": {"role": "textbox", "name": "Search"},
        "value": "Bengaluru",
        "risk": "low",
    }
    llm = FakeProvider([FakeResponse(name="d", schema_name="LLMDecision", response=decision)])
    ctx = StepContext(
        task="Search the map for Bengaluru",
        outline=[OutlineItem(seq=1, text="Search for the place")],
        page_snapshot=OSM_PAGE,
        path="/",
    )

    got = await StepDecider(llm).decide(ctx, seq=1)

    assert got.step is not None
    assert (got.step.action.type, got.step.action.value) == ("fill", "Bengaluru")
    assert (got.step.target.role, got.step.target.name) == ("textbox", "Search")
    assert got.step.expected_state.model_dump(exclude_none=True) == {}
    assert got.step.instruction_text.startswith("Enter")
    assert got.outline_seq == 1 and got.thought == "The search box is empty."
    system, prompt, _ = llm.calls[0]
    assert system == DECIDE_SYSTEM
    assert "1. Search for the place" in prompt and "(none yet)" in prompt


async def test_done_means_no_step() -> None:
    reply = {"thought": "The map shows Bengaluru.", "action": "done"}
    llm = FakeProvider([FakeResponse(name="d", schema_name="LLMDecision", response=reply)])
    ctx = StepContext(task="t", outline=[OutlineItem(seq=1, text="Search")])

    assert (await StepDecider(llm).decide(ctx, seq=3)).step is None


def decision(action: str, role: str | None, value: str | None = None) -> LLMDecision:
    target = DecidedTarget(role=role, name="X") if role else None
    return LLMDecision(thought="t", action=action, target=target, value=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # spike #457: qwen2.5 chose the right element with the wrong verb
        (decision("press", "button", ""), ("click", None)),
        (decision("press", "link", "/url: x"), ("click", None)),
        (decision("check", "button"), ("click", None)),
        (decision("check", "checkbox"), ("click", None)),
        (decision("press", "textbox", None), ("press", "Enter")),
        (decision("press", "textbox", "Enter"), ("press", "Enter")),
        (decision("fill", "textbox", "milk"), ("fill", "milk")),
    ],
)
def test_the_normaliser_fixes_verb_slips(raw: LLMDecision, expected: tuple[str, str | None]) -> None:
    fixed = normalize(raw)
    assert (fixed.action, fixed.value) == expected


def test_press_without_a_target_still_runs() -> None:
    # Gemini's one miss in the spike: Enter with no target, after typing in a field.
    step = to_step(decision("press", None, None), 2)
    assert step is not None and step.action.value == "Enter" and step.target.role is None
    assert step.instruction_text == "Press “Enter”."
