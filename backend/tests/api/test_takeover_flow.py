"""Human takeover end to end (#408, #409, #410, #414; ADR 0008): the API routes, the screen WebSocket, the
policy's pause at a sign-in wall and the hand-back checks, with real Postgres and Chromium (test site)."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi import WebSocketDisconnect

from app.api.accounts import SessionLimits, start_session
from app.api.takeover import CLOSE_FORBIDDEN, CLOSE_TAKEN, screen
from app.config import get_settings
from app.contracts_gen.run_schema import Run
from app.contracts_gen.takeover_schema import TakeoverKey, TakeoverMouse, TakeoverText
from app.contracts_gen.workflow_schema import Workflow
from app.policy import PolicyService
from app.runs.executor import InProcessExecutor
from tests.api.test_flow import Api, Sessions, make_user, reply, services
from tests.runs.test_runner import GOOD_PLAN, ITEM_NAME, step

pytestmark = pytest.mark.anyio

WALL_PLAN: dict[str, Any] = {
    "expected_result": "The new item form is open.",
    "steps": [
        step(
            1,
            {"type": "navigate", "value": "/wall"},
            {},
            "Open the members area.",
            {"url_matches": "^/wall$"},
        ),
        step(
            2,
            {"type": "click"},
            {"role": "link", "name": "New item"},
            "Click New item.",
            {"url_matches": "^/form$", "visible": [ITEM_NAME]},
        ),
    ],
}


def executor(api: Api) -> InProcessExecutor:
    assert isinstance(api.svc.executor, InProcessExecutor)
    return api.svc.executor


async def start(api: Api, site: str) -> UUID:
    task = await api.planned_task(site)
    approved = await api.client.post(f"/plans/{task.plan_id}/approve", json={"revision": 1})
    return Run.model_validate(approved.json()).id


async def wait_status(api: Api, run_id: UUID, status: str) -> Run:
    for _ in range(400):
        run = Run.model_validate((await api.client.get(f"/runs/{run_id}")).json())
        if run.status == status:
            return run
        await asyncio.sleep(0.05)
    raise AssertionError(f"never {status}: {run.status}")


async def click(api: Api, run_id: UUID, selector: str) -> None:
    """What the owner's browser sends for a click on `selector` (found on the live page for the test)."""
    session = executor(api).takeover(run_id)
    pausable = executor(api)._takeover_pages[run_id]
    box = await pausable.page.locator(selector).bounding_box()
    assert session is not None and box is not None
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await session.handle(TakeoverMouse(type="mouse", event="down", x=x, y=y))
    await session.handle(TakeoverMouse(type="mouse", event="up", x=x, y=y))


async def test_a_sign_in_wall_pauses_and_the_owner_signs_in_by_hand(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    svc = services(sessions, tmp_path, reply(WALL_PLAN), policy=PolicyService())
    async with Api(svc) as api:
        run_id = await start(api, site)
        paused = await wait_status(api, run_id, "paused")
        assert paused.current_seq == 2

        taken = await api.client.post(f"/runs/{run_id}/takeover")
        assert taken.status_code == 200, taken.text
        run = Run.model_validate(taken.json())
        assert run.status == "paused" and run.takeover is not None and run.takeover.step_seq == 2
        again = await api.client.post(f"/runs/{run_id}/takeover")
        assert again.status_code == 409 and again.json()["error"]["details"]["reason"] == "takeover_active"

        session = executor(api).takeover(run_id)
        assert session is not None
        await click(api, run_id, "input[name=user]")
        await session.handle(TakeoverText(type="text", text="demo"))
        await click(api, run_id, "input[name=pw]")
        await session.handle(TakeoverText(type="text", text="a secret only the owner types"))
        await session.handle(TakeoverKey(type="key", event="down", key="Enter"))
        page = executor(api)._takeover_pages[run_id].page
        await page.wait_for_url("**/members**")

        handed = await api.client.post(f"/runs/{run_id}/handback", json={"step_seq": 2, "done": "barrier"})
        assert handed.status_code == 200, handed.text
        stream = await api.events(run_id)

    types = [e["type"] for e in stream]
    pause = stream[types.index("run.paused")]
    assert (pause["reason"], pause["takeover_available"]) == ("auth_wall", True)
    ended = stream[types.index("takeover.ended")]
    assert (ended["reason"], ended["done"]) == ("handed_back", "barrier")
    assert types[-1] == "run.completed", stream[-1]
    assert "a secret only the owner types" not in json.dumps(stream)


async def test_a_step_done_by_hand_is_verified_without_acting_and_stored_as_human(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    broken = {
        **GOOD_PLAN,
        "steps": [
            *GOOD_PLAN["steps"][:2],
            {**GOOD_PLAN["steps"][2], "target": {"role": "checkbox", "name": "Gone"}},
            GOOD_PLAN["steps"][3],
        ],
    }
    async with Api(services(sessions, tmp_path, reply(broken))) as api:
        run_id = await start(api, site)
        paused = await wait_status(api, run_id, "paused")
        assert paused.current_seq == 3
        assert (await api.client.post(f"/runs/{run_id}/takeover")).status_code == 200

        await click(api, run_id, "input[name=init]")  # the owner ticks the box the plan couldn't find
        handed = await api.client.post(f"/runs/{run_id}/handback", json={"step_seq": 3, "done": "step"})
        assert handed.status_code == 200, handed.text
        stream = await api.events(run_id)
        assert stream[-1]["type"] == "run.completed", stream[-1]
        workflow = Workflow.model_validate(
            (await api.client.get(f"/workflows/{stream[-1]['workflow_id']}")).json()
        )

    human = [e for e in stream if e["type"] == "step.verified" and e.get("performed_by") == "human"]
    assert [e["step_seq"] for e in human] == [3] and human[0]["confidence"] <= 0.7
    by = {s.seq: s.performed_by for s in workflow.steps}
    assert by == {1: "krama", 2: "krama", 3: "human", 4: "krama"}
    assert workflow.steps[2].verification.confidence <= 0.7


async def test_hand_back_without_a_takeover_and_strangers_are_refused(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    risky = {
        **GOOD_PLAN,
        "steps": [*GOOD_PLAN["steps"][:2], {**GOOD_PLAN["steps"][2], "risk": "high"}, GOOD_PLAN["steps"][3]],
    }
    svc = services(sessions, tmp_path, reply(risky))
    async with Api(svc) as api:
        run_id = await start(api, site)
        await wait_status(api, run_id, "paused")  # destructive_action: no takeover offered
        refused = await api.client.post(f"/runs/{run_id}/takeover")
        handed = await api.client.post(f"/runs/{run_id}/handback", json={"step_seq": 3, "done": "step"})
        async with Api(svc, await make_user(sessions)) as other:
            stranger = await other.client.post(f"/runs/{run_id}/takeover")
        await api.client.post(f"/runs/{run_id}/cancel")

    assert refused.status_code == handed.status_code == 409
    assert refused.json()["error"]["code"] == "run_not_active"
    assert stranger.status_code == 404


# --- the screen WebSocket, driven with a stand-in socket in the test's own event loop


class FakeSocket:
    def __init__(self, api: Api, *, origin: str | None = None, cookie: str | None = None) -> None:
        settings = get_settings()
        self.app = SimpleNamespace(state=SimpleNamespace(services=api.svc))
        self.headers = {"origin": origin if origin is not None else settings.cors_origins[0]}
        token = cookie if cookie is not None else api.client.cookies.get("krama_session")
        self.cookies = {settings.session_cookie_name: token} if token else {}
        self.inbox: asyncio.Queue[str | None] = asyncio.Queue()
        self.texts: list[dict[str, Any]] = []
        self.frames = 0
        self.closed: int | None = None
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000) -> None:
        self.closed = code
        await self.inbox.put(None)

    async def send_text(self, text: str) -> None:
        self.texts.append(json.loads(text))

    async def send_bytes(self, data: bytes) -> None:
        assert data.startswith(b"\xff\xd8")
        self.frames += 1

    async def receive_text(self) -> str:
        item = await self.inbox.get()
        if item is None:
            raise WebSocketDisconnect()
        return item


async def test_the_screen_socket_streams_frames_takes_input_and_checks_who_connects(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    broken = {
        **GOOD_PLAN,
        "steps": [
            *GOOD_PLAN["steps"][:2],
            {**GOOD_PLAN["steps"][2], "target": {"role": "checkbox", "name": "Gone"}},
            GOOD_PLAN["steps"][3],
        ],
    }
    svc = services(sessions, tmp_path, reply(broken))
    async with Api(svc) as api:
        run_id = await start(api, site)
        await wait_status(api, run_id, "paused")

        early = FakeSocket(api)
        await screen(early, run_id)  # type: ignore[arg-type]
        assert early.closed == CLOSE_TAKEN and not early.accepted  # no takeover yet

        assert (await api.client.post(f"/runs/{run_id}/takeover")).status_code == 200
        for bad in (FakeSocket(api, origin="https://evil.example"), FakeSocket(api, cookie="")):
            await screen(bad, run_id)  # type: ignore[arg-type]
            assert bad.closed == CLOSE_FORBIDDEN
        async with (
            svc.sessions.begin() as s
        ):  # another account's session (a second Api would stop the services)
            token = await start_session(s, await make_user(sessions), SessionLimits())
        stranger = FakeSocket(api, cookie=token)
        await screen(stranger, run_id)  # type: ignore[arg-type]
        assert stranger.closed == CLOSE_FORBIDDEN

        viewer = FakeSocket(api)
        watching = asyncio.create_task(screen(viewer, run_id))  # type: ignore[arg-type]
        for _ in range(200):
            if viewer.frames:
                break
            await asyncio.sleep(0.05)
        second = FakeSocket(api)
        await screen(second, run_id)  # type: ignore[arg-type]
        await viewer.inbox.put('{"type": "wat"}')
        await viewer.inbox.put('{"type": "text", "text": "x"}')
        await asyncio.sleep(0.3)
        await viewer.inbox.put(None)  # the viewer closes the tab
        await watching
        run = Run.model_validate((await api.client.get(f"/runs/{run_id}")).json())
        await api.client.post(f"/runs/{run_id}/cancel")

    assert viewer.accepted and viewer.frames >= 1
    assert viewer.texts[0]["type"] == "ready" and (viewer.texts[0]["width"], viewer.texts[0]["height"]) == (
        1280,
        800,
    )
    assert any(t["type"] == "blocked" for t in viewer.texts)  # the input it didn't understand
    assert second.closed == CLOSE_TAKEN  # one viewer at a time
    assert (
        run.status == "paused" and run.takeover is None
    )  # closing the screen ends the takeover, not the run
