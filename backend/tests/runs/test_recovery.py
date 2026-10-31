"""Retry → replan → pause (#55), with the budget agreed in #43.

See docs/research/phase-1-vishwas-agent-recovery.md. Real Postgres, real Chromium on the local site; the
replanner is the real LLMPlanner with a recorded LLM reply.
"""

import asyncio
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent import SessionConfig
from app.agent.gitea_create_repo import login_steps
from app.db import PlanRow, WorkflowRow
from app.llm import FakeProvider, FakeResponse
from app.planner import LLMPlanner
from app.runs import InProcessExecutor, RunStore
from tests.runs.test_executor import (
    GITEA,
    _gitea_up,
    environment,
    events,
    finished,
    queued_run,
    run_row,
    until,
    until_paused,
)
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("stop_runs")]

Sessions = async_sessionmaker[AsyncSession]
OPEN_FORM = GOOD_PLAN["steps"][0]  # click "New item" → /form
MISSING = step(
    2,
    {"type": "click"},
    {"role": "button", "name": "Submit now"},
    "Click Submit now.",
    {"url_matches": "^/done$"},
)  # fmt: skip  (there is no such button: the click fails)
CREATE = {"role": "button", "name": "Create item"}
REPLAN = {
    "expected_result": "The item is created.",
    "steps": [step(1, {"type": "click"}, CREATE, "Click Create item.", {"url_matches": "^/done$"})],
}


def replanner(*responses: dict[str, Any]) -> tuple[LLMPlanner, FakeProvider]:
    llm = FakeProvider(
        [FakeResponse(name=f"r{i}", schema_name="LLMPlan", prompt_contains=["RE-PLANNING"], response=r)
         for i, r in enumerate(responses)]
    )  # fmt: skip
    return LLMPlanner(llm, max_attempts=1), llm


async def types(sessions: Sessions, run_id: UUID) -> list[str]:
    return [e["type"] for e in await events(sessions, run_id)]


async def last(sessions: Sessions, run_id: UUID) -> dict[str, Any]:
    return (await events(sessions, run_id))[-1]


async def exhausted(sessions: Sessions, run_id: UUID) -> bool:
    event = await last(sessions, run_id)
    return bool(event["type"] == "run.paused" and event["reason"] == "recovery_exhausted")


async def paused_twice(sessions: Sessions, run_id: UUID) -> bool:
    return (await types(sessions, run_id)).count("run.paused") == 2


async def test_an_idempotent_step_is_retried_once(sessions: Sessions, site: str, tmp_path: Path) -> None:
    wait = step(2, {"type": "wait"}, {"role": "button", "name": "Ready"}, "Wait for Ready.",
                {"visible": [{"role": "button", "name": "Ready"}]})  # fmt: skip
    nav = step(
        1, {"type": "navigate", "value": "/late"}, {}, "Open the late page.", {"url_matches": "^/late$"}
    )
    run_id = await queued_run(sessions, site, [nav, wait])
    env = environment(
        tmp_path,
        session_config=lambda job: SessionConfig(base_url=job.target_url, action_timeout_ms=1_000),
        verify_timeout_s=0.3,
    )
    executor = InProcessExecutor(RunStore(sessions), env)

    await executor.submit(run_id)
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "verified" and run.retry_count == 1
    stream = await types(sessions, run_id)
    assert stream.count("step.started") == 3  # step 2 twice
    assert "run.replanning" not in stream and "run.paused" not in stream


async def test_a_failed_click_is_replanned_and_the_human_approves_the_new_steps(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    planner, llm = replanner(REPLAN)
    run_id = await queued_run(sessions, site, [OPEN_FORM, MISSING])
    original_plan = (await run_row(sessions, run_id)).plan_id
    executor = InProcessExecutor(
        RunStore(sessions), environment(tmp_path, planner=planner, verify_timeout_s=0.3)
    )

    await executor.submit(run_id)
    await until_paused(sessions, run_id)

    paused = await last(sessions, run_id)
    assert (paused["reason"], paused["step_seq"]) == ("replan_review", 2)
    async with sessions() as s:
        proposal = await s.get(PlanRow, UUID(paused["plan_id"]))
        assert proposal is not None and proposal.status == "proposed"
        assert [st["instruction_text"] for st in proposal.steps] == ["Click New item.", "Click Create item."]
        assert [st["seq"] for st in proposal.steps] == [1, 2]
    stream = await events(sessions, run_id)
    replanning = next(e for e in stream if e["type"] == "run.replanning")
    assert replanning["attempt"] == 1 and "step 2 failed" in replanning["reason"]

    # The replan prompt: done steps as plain text, the failure as an untrusted block, the CURRENT page.
    prompt = llm.calls[0][1]
    assert "1. Click New item." in prompt and '<failure untrusted="true">' in prompt
    assert "target_not_found" in prompt and "Current URL path: /form" in prompt

    assert await executor.confirm(run_id, 2, "allow")
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "verified" and run.retry_count == 1
    assert run.plan_id == proposal.id != original_plan  # the run now follows the approved replan
    async with sessions() as s:
        adopted = await s.get(PlanRow, proposal.id)
        assert adopted is not None and adopted.status == "approved"
        workflow = await s.scalar(select(WorkflowRow).where(WorkflowRow.run_id == run_id))
        assert workflow is not None
    assert (await types(sessions, run_id))[-1] == "run.completed"


async def test_denying_a_replan_cancels_the_run(sessions: Sessions, site: str, tmp_path: Path) -> None:
    planner, _ = replanner(REPLAN)
    run_id = await queued_run(sessions, site, [OPEN_FORM, MISSING])
    executor = InProcessExecutor(
        RunStore(sessions), environment(tmp_path, planner=planner, verify_timeout_s=0.3)
    )
    await executor.submit(run_id)
    await until_paused(sessions, run_id)
    proposal = UUID((await last(sessions, run_id))["plan_id"])

    assert await executor.confirm(run_id, 2, "deny")
    await finished(executor, run_id)

    assert (await run_row(sessions, run_id)).status == "cancelled"
    async with sessions() as s:
        plan = await s.get(PlanRow, proposal)
        assert plan is not None and plan.status == "proposed"  # never approved


async def test_two_failed_steps_in_a_row_pause_instead_of_replanning_again(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    still_missing = {**REPLAN, "steps": [{**MISSING, "seq": 1}]}  # the replan proposes a step that fails too
    planner, llm = replanner(still_missing)
    run_id = await queued_run(sessions, site, [OPEN_FORM, MISSING])
    executor = InProcessExecutor(
        RunStore(sessions), environment(tmp_path, planner=planner, verify_timeout_s=0.3)
    )
    await executor.submit(run_id)
    await until_paused(sessions, run_id)
    assert await executor.confirm(run_id, 2, "allow")  # approve the (bad) replan

    await until(lambda: exhausted(sessions, run_id), "the recovery_exhausted pause")
    assert "two steps failed in a row" in (await last(sessions, run_id))["message"]
    assert len(llm.calls) == 1  # no second replan
    assert await executor.confirm(run_id, 2, "deny")
    await finished(executor, run_id)


async def test_the_replan_budget_comes_from_settings(sessions: Sessions, site: str, tmp_path: Path) -> None:
    planner, llm = replanner(REPLAN)
    run_id = await queued_run(sessions, site, [OPEN_FORM, MISSING])
    env = environment(tmp_path, planner=planner, max_replans_per_run=0, verify_timeout_s=0.3)
    executor = InProcessExecutor(RunStore(sessions), env)
    await executor.submit(run_id)
    await until_paused(sessions, run_id)

    paused = await last(sessions, run_id)
    assert paused["reason"] == "recovery_exhausted" and "budget is used up" in paused["message"]
    assert llm.calls == [] and "run.replanning" not in await types(sessions, run_id)

    # "Allow" tries the step once more; it fails again and pauses again: never a loop without a human.
    assert await executor.confirm(run_id, 2, "allow")
    await until(lambda: paused_twice(sessions, run_id), "a second pause")
    assert (await last(sessions, run_id))["reason"] == "recovery_exhausted"
    assert (await run_row(sessions, run_id)).retry_count == 1
    assert await executor.confirm(run_id, 2, "deny")
    await finished(executor, run_id)


async def test_a_failed_high_risk_step_is_never_replanned(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    planner, llm = replanner(REPLAN)
    run_id = await queued_run(sessions, site, [OPEN_FORM, {**MISSING, "risk": "high"}])
    executor = InProcessExecutor(
        RunStore(sessions), environment(tmp_path, planner=planner, verify_timeout_s=0.3)
    )
    await executor.submit(run_id)
    await until_paused(sessions, run_id)
    assert (await last(sessions, run_id))["reason"] == "destructive_action"  # #59: confirm first
    assert await executor.confirm(run_id, 2, "allow")

    await until(lambda: exhausted(sessions, run_id), "the recovery_exhausted pause")
    assert "high-risk" in (await last(sessions, run_id))["message"] and llm.calls == []
    assert await executor.confirm(run_id, 2, "deny")
    await finished(executor, run_id)


async def test_an_unclear_step_pauses_and_a_human_can_accept_it(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    unclear = step(
        1,
        {"type": "click"},
        {"role": "link", "name": "New item"},
        "Click New item.",
        {"title_contains": "item"},
    )  # fmt: skip  (nothing proves the click worked)
    run_id = await queued_run(sessions, site, [unclear])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, verify_timeout_s=0.3))
    await executor.submit(run_id)
    await until_paused(sessions, run_id)
    assert (await last(sessions, run_id))["reason"] == "verification_unclear"

    assert await executor.confirm(run_id, 1, "allow")
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "verified"
    async with sessions() as s:
        workflow = await s.scalar(select(WorkflowRow).where(WorkflowRow.run_id == run_id))
        assert workflow is not None and workflow.confidence is not None
        assert workflow.confidence < 0.8  # human-accepted, not machine-verified


async def test_the_run_timeout_ends_a_run(sessions: Sessions, site: str, tmp_path: Path) -> None:
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, run_timeout_s=0.0))

    await executor.submit(run_id)
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "run_timeout", "step_seq": 1}


@pytest.mark.skipif(
    os.environ.get("KRAMA_LIVE_GEMINI") != "1" or not _gitea_up(),
    reason="live Gemini + Gitea; set KRAMA_LIVE_GEMINI=1 and `just up`",
)
async def test_live_gemini_replans_a_wrong_button_on_real_gitea(sessions: Sessions, tmp_path: Path) -> None:
    from app.config import get_settings
    from app.llm import DEFAULT_MODELS, GeminiProvider
    from app.targets import target_setup

    settings = get_settings()
    user, name = settings.gitea_demo_user, f"krama-replan-{uuid.uuid4().hex[:6]}"
    box = {"role": "textbox", "name": "Repository Name"}
    plan = [
        step(1, {"type": "navigate", "value": "/repo/create"}, {}, "Open.", {"url_matches": "^/repo/"}),
        step(2, {"type": "fill", "value": name}, box, "Name.", {"field_values": [{**box, "value": name}]}),
        step(3, {"type": "click"}, {"role": "button", "name": "Build Repository"}, "Click Build Repository.",
             {"url_matches": f"^/{user}/{name}$"}),  # no such button: the click fails
    ]  # fmt: skip
    run_id = await queued_run(sessions, GITEA, plan, prompt=f"Create a repository called {name}")
    env = environment(
        tmp_path,
        preconditions=lambda _job: login_steps(user=user, password=settings.gitea_demo_password),
        planner=LLMPlanner(GeminiProvider(settings.gemini_api_key, DEFAULT_MODELS)),
        target=lambda job: target_setup(job.target_url, settings),
    )
    executor = InProcessExecutor(RunStore(sessions), env)
    try:
        await executor.submit(run_id)
        await until_paused(sessions, run_id, timeout_s=180)  # a real Gemini replan takes ~20-60 s

        paused = await last(sessions, run_id)
        assert paused["reason"] == "replan_review", paused.get("message")
        async with sessions() as s:
            proposal = await s.get(PlanRow, UUID(paused["plan_id"]))
            assert proposal is not None
        print(
            "REPLAN", [(st["seq"], st["action"], st["target"], st["expected_state"]) for st in proposal.steps]
        )
        assert await executor.confirm(run_id, 3, "allow")
        await finished(executor, run_id)
    finally:
        await executor.shutdown()  # never leave a paused browser behind, even when an assert fails

    run = await run_row(sessions, run_id)
    assert run.status == "verified", run.error
    url = f"{GITEA}/api/v1/repos/{user}/{name}"
    assert await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=5).status) == 200
