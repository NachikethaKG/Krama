"""Step mode end to end (#470, ADR 0011): real Postgres, Chromium, observer and verifier on the local site;
the decisions come from a script instead of an LLM."""

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db import PlanRow, RunRow, TaskRow, WorkflowStepRow
from app.planner.stepwise import DecidedTarget, Decision, LLMDecision, StepContext, to_step
from app.runs import InProcessExecutor, RunStore
from app.runs.reverify import create_reverify_run
from app.verifier.task_check import TaskVerdict
from tests.runs.test_executor import Sessions, environment, events, finished, run_to_end, until_paused

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("stop_runs")]


class ScriptedDecider:
    """Returns the next scripted decision each time; remembers what it was shown."""

    def __init__(self, *script: tuple[str, str | None, str | None, str | None]) -> None:
        self.script = list(script)
        self.seen: list[StepContext] = []

    async def decide(self, ctx: StepContext, *, seq: int) -> Decision:
        self.seen.append(ctx)
        action, role, name, value = self.script.pop(0) if self.script else ("done", None, None, None)
        target = DecidedTarget(role=role, name=name) if role and name else None
        raw = LLMDecision(thought=f"step {seq}", outline_seq=1, action=action, target=target, value=value)
        return Decision(
            thought=raw.thought, outline_seq=1, step=to_step(raw, seq), model="script", llm_attempts=[]
        )


async def step_mode_run(sessions: Sessions, site: str) -> UUID:
    async with sessions.begin() as s:
        task = TaskRow(prompt="Create an item called demo-item", target_url=site, status="planned")
        s.add(task)
        await s.flush()
        plan = PlanRow(
            task_id=task.id, status="approved", risk="low", expected_result="The item exists.", steps=[],
            mode="steps", outline=[{"seq": 1, "text": "Create the item"}], title="Create an item",
        )  # fmt: skip
        s.add(plan)
        await s.flush()
        run = RunRow(plan_id=plan.id, plan_revision=1, status="queued")
        s.add(run)
        await s.flush()
        return run.id


async def stored_steps(sessions: Sessions, run_id: UUID) -> list[WorkflowStepRow]:
    completed = [e for e in await events(sessions, run_id) if e["type"] == "run.completed"]
    workflow_id = UUID(completed[0]["workflow_id"])
    async with sessions() as s:
        query = select(WorkflowStepRow).where(WorkflowStepRow.workflow_id == workflow_id)
        return list(await s.scalars(query.order_by(WorkflowStepRow.seq)))


async def test_a_step_mode_run_records_what_each_action_changed(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    decider = ScriptedDecider(
        ("click", "link", "New item", None),
        ("fill", "textbox", "Item name *", "demo-item"),
        ("click", "button", "Create item", None),
    )
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, decider=decider))
    run_id = await step_mode_run(sessions, site)

    await run_to_end(executor, run_id)

    got = await events(sessions, run_id)
    types = [e["type"] for e in got]
    assert types[-1] == "run.completed", got[-1]
    assert got[0]["total_steps"] == 1  # the outline stands for the steps
    assert types.count("step.decided") == 3 and types.count("step.verified") == 3
    steps = await stored_steps(sessions, run_id)
    assert [s.seq for s in steps] == [1, 2, 3]
    assert {s.section for s in steps} == {"Create the item"}  # the outline item, as a section title (#471)
    expected: list[dict[str, Any]] = [s.expected_state for s in steps]
    assert expected[0]["url_matches"] == "^/form$"
    assert expected[1]["field_values"] == [{"role": "textbox", "name": "Item name *", "value": "demo-item"}]
    assert expected[2]["url_matches"] == "^/done$"
    # The decider saw each step that worked, and the page as untrusted text.
    assert decider.seen[-1].done == [s.instruction_text for s in steps]
    assert 'heading "Item created"' in decider.seen[-1].page_snapshot


async def test_actions_that_change_nothing_pause_the_run(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    decider = ScriptedDecider(*[("click", "heading", "Home", None)] * 5)
    executor = InProcessExecutor(
        RunStore(sessions), environment(tmp_path, decider=decider, verify_timeout_s=0.5)
    )
    run_id = await step_mode_run(sessions, site)

    await executor.submit(run_id)
    await until_paused(sessions, run_id)

    got = await events(sessions, run_id)
    paused = [e for e in got if e["type"] == "run.paused"][-1]
    assert paused["reason"] == "no_progress" and paused["takeover_available"] is True
    assert len(decider.seen) == 3
    assert "Tried, not done" in decider.seen[-1].done[-1]
    await executor.cancel(run_id)
    await finished(executor, run_id)


async def test_done_before_any_step_fails_clearly(sessions: Sessions, site: str, tmp_path: Path) -> None:
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, decider=ScriptedDecider()))
    run_id = await step_mode_run(sessions, site)

    await run_to_end(executor, run_id)

    last = (await events(sessions, run_id))[-1]
    assert last["type"] == "run.failed" and last["error"]["details"]["reason"] == "nothing_to_do"


async def test_without_a_decider_a_step_mode_run_fails(sessions: Sessions, site: str, tmp_path: Path) -> None:
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))
    run_id = await step_mode_run(sessions, site)

    await run_to_end(executor, run_id)

    last = (await events(sessions, run_id))[-1]
    assert last["type"] == "run.failed" and last["error"]["details"]["reason"] == "no_decider"


async def test_a_step_mode_workflow_replays_without_a_decider(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    # #471: the stored steps carry the expected states they reached, so a replay needs no LLM.
    decider = ScriptedDecider(
        ("click", "link", "New item", None),
        ("fill", "textbox", "Item name *", "demo-item"),
        ("click", "button", "Create item", None),
    )
    recorder = InProcessExecutor(RunStore(sessions), environment(tmp_path, decider=decider))
    run_id = await step_mode_run(sessions, site)
    await run_to_end(recorder, run_id)
    completed = [e for e in await events(sessions, run_id) if e["type"] == "run.completed"]
    workflow_id = UUID(completed[0]["workflow_id"])

    replayer = InProcessExecutor(RunStore(sessions), environment(tmp_path / "replay"))  # no decider at all
    replay = await create_reverify_run(sessions, workflow_id, None)
    await run_to_end(replayer, replay)

    got = await events(sessions, replay)
    assert got[-1]["type"] == "run.completed", got[-1]
    assert [e["type"] for e in got].count("step.verified") == 3
    assert "step.decided" not in [e["type"] for e in got]


class DoneCheck:
    """A task check that answers `done` and counts how often it was asked."""

    def __init__(self, done: bool) -> None:
        self.done, self.asked = done, 0

    async def check(self, task: str, steps: Any, final_path: str, final_page: str) -> TaskVerdict:
        self.asked += 1
        return TaskVerdict(done=self.done, missing="" if self.done else "the rest", attempts=[])


async def test_waiting_after_the_work_asks_the_task_check(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    # OSM on qwen2.5: the search had worked, then the model kept waiting instead of answering done.
    decider = ScriptedDecider(("click", "link", "New item", None), *[("wait", None, None, None)] * 4)
    check = DoneCheck(done=True)
    env = environment(tmp_path, decider=decider, task_check=check)
    executor = InProcessExecutor(RunStore(sessions), env)
    run_id = await step_mode_run(sessions, site)

    await run_to_end(executor, run_id)

    got = await events(sessions, run_id)
    assert got[-1]["type"] == "run.completed", got[-1]
    assert [e["type"] for e in got].count("step.verified") == 1
    assert "step.started" not in [e["type"] for e in got if e.get("step_seq") == 2]  # the wait never ran
    assert check.asked >= 1
