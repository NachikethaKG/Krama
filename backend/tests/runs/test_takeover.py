"""Human takeover (#407, ADR 0008): the session on a real headless Chromium and the executor's pause hooks."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from playwright.async_api import Page

from app.agent import PlaywrightSession, SessionConfig
from app.contracts_gen.takeover_schema import TakeoverKey, TakeoverMouse, TakeoverText
from app.runs.executor import InProcessExecutor, TakeoverError
from app.runs.takeover import TakeoverSession, host_of
from tests.api.test_flow import Api, Sessions, reply, services
from tests.runs.test_runner import GOOD_PLAN

pytestmark = pytest.mark.anyio

JPEG = b"\xff\xd8"


@pytest.fixture
async def page(site: str) -> AsyncIterator[Page]:
    async with PlaywrightSession(SessionConfig(base_url=site)) as session:
        await session.page.goto(f"{site}/form")
        yield session.page


class Recorder:
    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.blocked: list[str] = []
        self.ended: list[str] = []

    async def frame(self, data: bytes) -> None:
        self.frames.append(data)

    async def block(self, message: str) -> None:
        self.blocked.append(message)

    async def end(self, reason: str) -> None:
        self.ended.append(reason)

    def session(self, page: Page, site: str, **kw: Any) -> TakeoverSession:
        return TakeoverSession(
            page, allowed_hosts=[host_of(site)], on_end=self.end, on_blocked=self.block, **kw
        )


async def eventually(check: Any, seconds: float = 5.0) -> None:
    for _ in range(int(seconds / 0.05)):
        if check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition never held")


async def center(page: Page, selector: str) -> tuple[float, float]:
    box = await page.locator(selector).bounding_box()
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


async def test_frames_stream_as_jpeg_and_input_reaches_the_page(page: Page, site: str) -> None:
    rec = Recorder()
    session = rec.session(page, site)
    await session.start(rec.frame)
    await eventually(lambda: rec.frames)
    assert rec.frames[0].startswith(JPEG)

    x, y = await center(page, "input[name=item]")
    await session.handle(TakeoverMouse(type="mouse", event="down", x=x, y=y))
    await session.handle(TakeoverMouse(type="mouse", event="up", x=x, y=y))
    for key in "ab":
        await session.handle(TakeoverKey(type="key", event="down", key=key))
        await session.handle(TakeoverKey(type="key", event="up", key=key))
    await session.handle(TakeoverKey(type="key", event="down", key="Backspace"))
    await session.handle(TakeoverText(type="text", text="-pasted ✓"))
    await session.handle(TakeoverKey(type="key", event="down", key="NoSuchKey"))  # ignored, not fatal

    assert await page.locator("input[name=item]").input_value() == "a-pasted ✓"
    assert session.last_input_at is not None
    await session.end("handed_back")
    assert rec.ended == ["handed_back"]


async def test_frames_are_capped(page: Page, site: str) -> None:
    rec = Recorder()
    session = rec.session(page, site, max_fps=2)
    await page.evaluate(
        "() => { const d = document.createElement('div'); document.body.append(d);"
        " setInterval(() => { d.textContent = String(Date.now()) }, 16) }"
    )
    await session.start(rec.frame)
    await asyncio.sleep(2.0)
    await session.end("closed")

    assert 1 <= len(rec.frames) <= 6  # ~2 per second, never the page's ~60


async def test_navigation_outside_the_target_is_blocked(page: Page, site: str) -> None:
    rec = Recorder()
    session = rec.session(page, site)
    await session.start(rec.frame)

    await page.evaluate("() => { location.href = 'http://10.255.255.1:9/admin' }")
    await eventually(lambda: rec.blocked)
    await asyncio.sleep(0.5)  # an error page would have committed by now
    assert page.url == f"{site}/form"
    assert not session.allowed("file:///etc/passwd") and not session.allowed("chrome://settings")

    await page.goto(f"{site}/done")  # the target itself is fine (goto goes through the same guard)
    assert page.url == f"{site}/done"
    await session.end("closed")


async def test_new_tabs_are_closed(page: Page, site: str) -> None:
    rec = Recorder()
    session = rec.session(page, site)
    await session.start(rec.frame)

    await page.evaluate("() => window.open('/done')")
    await eventually(lambda: rec.blocked)
    await eventually(lambda: len(page.context.pages) == 1)
    await session.end("closed")


async def test_idle_ends_it_once_and_input_after_the_end_is_ignored(page: Page, site: str) -> None:
    rec = Recorder()
    session = rec.session(page, site, idle_s=0.3)
    await session.start(rec.frame)

    await eventually(lambda: rec.ended)
    await session.end("closed")
    await session.handle(TakeoverText(type="text", text="late"))

    assert rec.ended == ["idle"] and session.ended == "idle"
    assert await page.locator("input[name=item]").input_value() == ""


# --- the executor


async def paused_run(api: Api, site: str, *, risky: bool = False) -> UUID:
    """A run paused at step 3: verification_unclear (nothing to check), or destructive_action when `risky`."""
    task = await api.planned_task(site)
    step3: dict[str, Any] = {"risk": "high"} if risky else {"expected_state": {}}
    async with api.svc.sessions.begin() as s:
        from app.db import PlanRow

        plan = await s.get(PlanRow, task.plan_id)
        assert plan is not None
        steps = [dict(st) for st in plan.steps]
        steps[2] = {**steps[2], **step3}
        plan.steps = steps
    run_id = UUID(
        (await api.client.post(f"/plans/{task.plan_id}/approve", json={"revision": 1})).json()["id"]
    )
    for _ in range(400):
        if (await api.client.get(f"/runs/{run_id}")).json()["status"] == "paused":
            return run_id
        await asyncio.sleep(0.05)
    raise AssertionError("the run never paused")


def executor(api: Api) -> InProcessExecutor:
    assert isinstance(api.svc.executor, InProcessExecutor)
    return api.svc.executor


async def events_so_far(api: Api, run_id: UUID) -> list[dict[str, Any]]:
    from app.db.repositories import event_payload, events_after

    async with api.svc.sessions() as s:
        return [event_payload(e) for e in await events_after(s, run_id, 0)]


async def test_an_unclear_step_offers_a_takeover_and_records_it(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        run_id = await paused_run(api, site)
        rec = Recorder()

        session = await executor(api).start_takeover(run_id, rec.frame, on_end=rec.end)
        with pytest.raises(TakeoverError) as again:
            await executor(api).start_takeover(run_id, rec.frame)
        await eventually(lambda: rec.frames)
        assert executor(api).takeover(run_id) is session

        confirmed = await api.client.post(
            f"/runs/{run_id}/confirm", json={"step_seq": 3, "decision": "allow"}
        )
        assert confirmed.status_code == 200, confirmed.text
        stream = await api.events(run_id)

    assert again.value.reason == "active"
    assert rec.ended == ["closed"] and executor(api).takeover(run_id) is None
    types = [e["type"] for e in stream]
    paused = stream[types.index("run.paused")]
    assert (paused["reason"], paused.get("takeover_available")) == ("verification_unclear", True)
    i = types.index("takeover.started")
    assert types[i : i + 3] == ["takeover.started", "takeover.ended", "run.resumed"]
    assert stream[i + 1]["reason"] == "closed" and stream[i]["step_seq"] == 3
    assert types[-1] == "run.completed"


async def test_a_destructive_pause_offers_no_takeover(sessions: Sessions, tmp_path: Path, site: str) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        run_id = await paused_run(api, site, risky=True)
        with pytest.raises(TakeoverError) as refused:
            await executor(api).start_takeover(run_id, Recorder().frame)
        paused = [e for e in await events_so_far(api, run_id) if e["type"] == "run.paused"]
        await api.client.post(f"/runs/{run_id}/cancel")

    assert refused.value.reason == "not_available"
    assert paused[0]["reason"] == "destructive_action" and not paused[0].get("takeover_available")


async def test_cancelling_ends_the_takeover_without_events_after_the_end(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        run_id = await paused_run(api, site)
        rec = Recorder()
        await executor(api).start_takeover(run_id, rec.frame, on_end=rec.end)

        await api.client.post(f"/runs/{run_id}/cancel")
        stream = await api.events(run_id)

    assert rec.ended == ["cancelled"]
    assert stream[-1]["type"] == "run.cancelled"  # nothing after the final event


async def test_an_idle_takeover_ends_and_the_run_stays_paused(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN), takeover_idle_s=0.3)) as api:
        run_id = await paused_run(api, site)
        rec = Recorder()
        await executor(api).start_takeover(run_id, rec.frame, on_end=rec.end)

        await eventually(lambda: rec.ended)
        status = (await api.client.get(f"/runs/{run_id}")).json()["status"]
        ended = [e for e in await events_so_far(api, run_id) if e["type"] == "takeover.ended"]
        await api.client.post(f"/runs/{run_id}/cancel")

    assert rec.ended == ["idle"] and status == "paused"
    assert ended[0]["reason"] == "idle"
