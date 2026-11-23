"""Step mode through the API (#470, ADR 0011): POST /tasks → outline → approve → decided steps → workflow.

The real OutlinePlanner and StepDecider run on the fake LLM; each decision reply is chosen by what the page
shows, like a model looking at it."""

from pathlib import Path
from typing import Any

import pytest

from app.api.services import Services
from app.contracts_gen.plan_schema import Plan
from app.llm import FakeProvider, FakeResponse
from app.planner.stepwise import OutlinePlanner, StepDecider
from tests.api.test_flow import Api, Sessions, services

pytestmark = pytest.mark.anyio

OUTLINE = {
    "expected_result": "The item exists.",
    "title": "Create an item",
    "outline": ["Open the form", "Create the item"],
    "risk": "medium",
    "clarification_question": None,
}


def decide(
    action: str, role: str | None = None, name: str | None = None, value: str | None = None
) -> dict[str, Any]:
    target = {"role": role, "name": name} if role else None
    return {
        "thought": f"{action} {name}",
        "outline_seq": 1,
        "action": action,
        "target": target,
        "value": value,
    }


def decision(name: str, when: str, reply: dict[str, Any]) -> FakeResponse:
    return FakeResponse(name=name, schema_name="LLMDecision", prompt_contains=[when], response=reply)


# Most specific page first: FakeProvider takes the first reply whose words are all in the prompt.
DECISIONS = [
    decision("done", 'heading "Item created"', decide("done")),
    decision("submit", 'textbox "Item name *": demo-item', decide("click", "button", "Create item")),
    decision("name", 'heading "New item"', decide("fill", "textbox", "Item name *", "demo-item")),
    decision("open", 'heading "Home"', decide("click", "link", "New item")),
]


def step_services(sessions: Sessions, tmp_path: Path) -> Services:
    svc = services(sessions, tmp_path, decider=StepDecider(FakeProvider(DECISIONS)))
    outline = FakeResponse(name="outline", schema_name="LLMOutline", response=OUTLINE)
    svc.planning._planner = OutlinePlanner(FakeProvider([outline]))
    return svc


async def test_a_task_runs_from_an_approved_outline(sessions: Sessions, site: str, tmp_path: Path) -> None:
    async with Api(step_services(sessions, tmp_path)) as api:
        task = await api.planned_task(site)
        assert task.status == "planned"
        plan = Plan.model_validate((await api.client.get(f"/plans/{task.plan_id}")).json())
        assert plan.mode == "steps" and plan.steps == []
        assert [o.text for o in plan.outline or []] == ["Open the form", "Create the item"]

        edit = await api.client.patch(f"/plans/{plan.id}", json={"revision": 1, "steps": []})
        assert edit.status_code in (409, 422)  # an outline has no steps to edit

        run = (await api.client.post(f"/plans/{plan.id}/approve", json={"revision": plan.revision})).json()
        await api.svc.executor.wait(run["id"])
        events = await api.events(run["id"])

    types = [e["type"] for e in events]
    assert types[-1] == "run.completed", events[-1]
    assert types.count("step.decided") == 3 and types.count("step.verified") == 3
    decided = [e for e in events if e["type"] == "step.decided"]
    assert decided[1]["action"] == {"type": "fill", "value": "demo-item"}
    assert decided[1]["target"] == {"role": "textbox", "name": "Item name *"}
