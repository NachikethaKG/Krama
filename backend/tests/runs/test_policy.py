"""The Policy port in the run loop (#59): checked before every step; pause → /confirm; stop ends the run.

Real Postgres, real Chromium on the local site. The Policy is the port's FakePolicy until #61 lands.
"""

import asyncio
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.gitea_create_repo import login_steps
from app.db import WorkflowRow
from app.ports.fakes import FakePolicy
from app.ports.models import PolicyDecision
from app.runs import InProcessExecutor, RunStore
from app.runs.executor import PAUSE_REASONS
from tests.runs.test_executor import (
    GITEA,
    _gitea_up,
    environment,
    events,
    finished,
    queued_run,
    run_row,
    run_to_end,
)
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("stop_runs")]

Sessions = async_sessionmaker[AsyncSession]
# The same plan, with the final "Create item" click marked high risk by the planner.
RISKY = [*GOOD_PLAN["steps"][:3], {**GOOD_PLAN["steps"][3], "risk": "high"}]


async def until(sessions: Sessions, run_id: UUID, status: str) -> None:
    for _ in range(1200):
        if (await run_row(sessions, run_id)).status == status:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"run never became {status}: {(await run_row(sessions, run_id)).status}")


async def types(sessions: Sessions, run_id: UUID) -> list[str]:
    return [e["type"] for e in await events(sessions, run_id)]


async def test_a_high_risk_step_pauses_until_a_human_allows_it(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    run_id = await queued_run(sessions, site, RISKY)
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))

    await executor.submit(run_id)
    await until(sessions, run_id, "paused")

    stream = await events(sessions, run_id)
    paused = stream[-1]
    assert (paused["type"], paused["reason"], paused["step_seq"]) == ("run.paused", "destructive_action", 4)
    assert "high risk" in paused["message"]
    # Nothing of step 4 happened yet: no action_done for it.
    assert not any(e["type"] == "step.action_done" and e["step_seq"] == 4 for e in stream)

    assert not await executor.confirm(run_id, 3, "allow")  # not the paused step
    assert await executor.confirm(run_id, 4, "allow")
    await finished(executor, run_id)

    assert (await run_row(sessions, run_id)).status == "verified"
    after = await types(sessions, run_id)
    assert after[after.index("run.paused") + 1] == "run.resumed"
    assert after[-1] == "run.completed"
    assert not await executor.confirm(run_id, 4, "allow")  # finished: nothing to answer


async def test_deny_cancels_without_running_the_step(sessions: Sessions, site: str, tmp_path: Path) -> None:
    run_id = await queued_run(sessions, site, RISKY)
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))
    await executor.submit(run_id)
    await until(sessions, run_id, "paused")

    assert await executor.confirm(run_id, 4, "deny")
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "cancelled"
    stream = await events(sessions, run_id)
    assert stream[-1]["type"] == "run.cancelled"
    assert (stream[-1]["reason"], stream[-1]["step_seq"]) == ("confirmation_denied", 4)
    assert not any(e["type"] == "step.action_done" and e["step_seq"] == 4 for e in stream)
    async with sessions() as s:
        assert await s.scalar(select(func.count()).select_from(WorkflowRow)) == 0


async def test_the_policy_sees_each_step_and_the_page_before_it(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    policy = FakePolicy()
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, policy=policy))

    await executor.submit(run_id)
    await finished(executor, run_id)

    assert (await run_row(sessions, run_id)).status == "verified"
    assert [step.seq for step, _ in policy.checked] == [1, 2, 3, 4]
    first_page = policy.checked[0][1]
    assert (first_page.url, first_page.title) == ("/", "Home")  # before step 1, not after it
    assert 'link "New item"' in first_page.aria_excerpt


async def test_a_policy_pause_waits_for_confirm(sessions: Sessions, site: str, tmp_path: Path) -> None:
    pause = PolicyDecision(verdict="pause", reason="destructive_action", message="Deletes data")
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, policy=FakePolicy({2: pause})))

    await executor.submit(run_id)
    await until(sessions, run_id, "paused")
    assert (await events(sessions, run_id))[-1]["message"] == "Deletes data"
    assert await executor.confirm(run_id, 2, "allow")
    await finished(executor, run_id)

    assert (await run_row(sessions, run_id)).status == "verified"


async def test_a_policy_stop_ends_the_run_before_the_step(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    stop = PolicyDecision(verdict="stop", reason="captcha", message="A CAPTCHA blocks the page")
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, policy=FakePolicy({2: stop})))

    await executor.submit(run_id)
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["message"] == "A CAPTCHA blocks the page"
    assert run.error["details"] == {"reason": "policy_stop", "policy_reason": "captcha", "step_seq": 2}
    assert not any(
        e.get("step_seq") == 2 and e["type"] == "step.action_done" for e in await events(sessions, run_id)
    )


async def test_a_pause_the_contract_cannot_express_yet_never_continues(
    sessions: Sessions, site: str, tmp_path: Path
) -> None:
    odd = PolicyDecision(verdict="pause", reason="prompt_injection")
    run_id = await queued_run(sessions, site, GOOD_PLAN["steps"])
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path, policy=FakePolicy({1: odd})))

    await executor.submit(run_id)
    if "prompt_injection" in PAUSE_REASONS:  # after #216: a real pause
        await until(sessions, run_id, "paused")
        assert await executor.cancel(run_id)
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status in ("failed", "cancelled")
    assert "step.action_done" not in await types(sessions, run_id)


async def test_an_unanswered_pause_gives_up(sessions: Sessions, site: str, tmp_path: Path) -> None:
    run_id = await queued_run(sessions, site, RISKY)
    env = environment(tmp_path, pause_timeout_s=0.5)

    executor = InProcessExecutor(RunStore(sessions), env)
    await executor.submit(run_id)
    await finished(executor, run_id)

    run = await run_row(sessions, run_id)
    assert run.status == "failed" and run.error is not None
    assert run.error["details"] == {"reason": "pause_timeout", "step_seq": 4}


async def test_cancel_while_paused(sessions: Sessions, site: str, tmp_path: Path) -> None:
    run_id = await queued_run(sessions, site, RISKY)
    executor = InProcessExecutor(RunStore(sessions), environment(tmp_path))
    await executor.submit(run_id)
    await until(sessions, run_id, "paused")

    assert await executor.cancel(run_id)
    await finished(executor, run_id)

    stream: list[dict[str, Any]] = await events(sessions, run_id)
    assert (stream[-1]["type"], stream[-1]["reason"]) == ("run.cancelled", "user")
    assert not await executor.confirm(run_id, 4, "allow")


@pytest.mark.skipif(not _gitea_up(), reason=f"Gitea not reachable at {GITEA}; start it with `just up`")
async def test_deleting_a_real_gitea_repository_pauses_and_deny_keeps_it(
    sessions: Sessions, tmp_path: Path
) -> None:
    from app.config import get_settings

    settings = get_settings()
    user, name = settings.gitea_demo_user, f"krama-keep-{uuid.uuid4().hex[:8]}"
    env = environment(
        tmp_path, preconditions=lambda _job: login_steps(user=user, password=settings.gitea_demo_password)
    )
    repo_name = {"role": "textbox", "name": "Repository Name"}
    typed = {"field_values": [{**repo_name, "value": name}]}
    create = [
        step(1, {"type": "navigate", "value": "/repo/create"}, {}, "Open.", {"url_matches": "^/repo/"}),
        step(2, {"type": "fill", "value": name}, repo_name, "Name.", typed),
        step(3, {"type": "click"}, {"role": "button", "name": "Create Repository"}, "Create.",
             {"url_matches": f"^/{user}/{name}$"}),
    ]  # fmt: skip
    first = await queued_run(sessions, GITEA, create)
    await run_to_end(InProcessExecutor(RunStore(sessions), env), first)
    assert (await run_row(sessions, first)).status == "verified"

    delete = [
        step(1, {"type": "navigate", "value": f"/{user}/{name}/settings"}, {}, "Open the settings.",
             {"url_matches": f"^/{user}/{name}/settings$"}),
        {**step(2, {"type": "click"}, {"role": "button", "name": "Delete This Repository"}, "Delete it.",
                {"visible": [{"role": "button", "name": "Delete Repository"}]}), "risk": "high"},
    ]  # fmt: skip
    run_id = await queued_run(sessions, GITEA, delete)
    executor = InProcessExecutor(RunStore(sessions), env)
    await executor.submit(run_id)
    await until(sessions, run_id, "paused")
    assert (await events(sessions, run_id))[-1]["step_seq"] == 2

    assert await executor.confirm(run_id, 2, "deny")
    await finished(executor, run_id)

    assert (await run_row(sessions, run_id)).status == "cancelled"
    url = f"{GITEA}/api/v1/repos/{user}/{name}"
    assert (
        await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=5).status) == 200
    )  # still there
