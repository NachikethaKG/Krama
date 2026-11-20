"""Takeover across processes (#413): the API's relay and the worker's relay over a real Redis, with a stand-in
for the worker's executor (the browser side is covered in test_takeover.py)."""

import asyncio
import contextlib
from typing import Any
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis

from app.contracts_gen.takeover_schema import TakeoverText
from app.runs.takeover import TakeoverError
from app.runs.takeover_relay import ApiTakeoverRelay, WorkerTakeoverRelay
from tests.runs.test_worker import REDIS_URL, redis_up

pytestmark = pytest.mark.anyio


class StubSession:
    def __init__(self, step_seq: int) -> None:
        self.step_seq = step_seq
        self.ended: str | None = None
        self.inputs: list[Any] = []

    async def handle(self, message: Any) -> None:
        self.inputs.append(message)


class StubExecutor:
    """What the worker's InProcessExecutor offers the relay."""

    def __init__(self) -> None:
        self.sessions: dict[UUID, StubSession] = {}
        self.ends: dict[UUID, Any] = {}
        self.frames: dict[UUID, Any] = {}
        self.handbacks: list[tuple[UUID, int, str]] = []

    async def start_takeover(
        self, run_id: UUID, on_frame: Any, *, on_blocked: Any, on_end: Any
    ) -> StubSession:
        if run_id in self.sessions:
            raise TakeoverError("active", "Someone already has control of this run")
        self.sessions[run_id] = StubSession(3)
        self.ends[run_id], self.frames[run_id] = on_end, on_frame
        return self.sessions[run_id]

    async def hand_back(self, run_id: UUID, step_seq: int, done: str) -> bool:
        self.handbacks.append((run_id, step_seq, done))
        return step_seq == 3

    async def end_takeover(self, run_id: UUID, reason: str) -> None:
        session = self.sessions.get(run_id)
        if session is not None and session.ended is None:
            session.ended = reason
            await self.ends[run_id](reason)


@pytest.fixture
async def relays() -> Any:
    if not await redis_up():
        pytest.skip(f"Redis isn't reachable at {REDIS_URL} (`just up`)")
    stub = StubExecutor()
    worker = asyncio.create_task(WorkerTakeoverRelay(REDIS_URL, stub).run())
    await asyncio.sleep(0.3)  # subscribed
    redis = Redis.from_url(REDIS_URL)

    async def factory() -> Redis:
        return redis

    yield stub, ApiTakeoverRelay(factory)
    worker.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await worker
    await redis.aclose()


async def eventually(check: Any) -> None:
    for _ in range(100):
        if check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition never held")


async def test_frames_input_hand_back_and_end_cross_redis(relays: Any) -> None:
    stub, api = relays
    run_id = uuid4()
    frames: list[bytes] = []
    blocked: list[str] = []
    ended: list[str] = []

    async def on_frame(data: bytes) -> None:
        frames.append(data)

    async def on_blocked(message: str) -> None:
        blocked.append(message)

    async def on_end(reason: str) -> None:
        ended.append(reason)

    remote = await api.start(run_id, on_frame, on_blocked, on_end)
    assert remote.step_seq == 3 and api.takeover(run_id) is remote

    await stub.frames[run_id](b"\xff\xd8 a jpeg")
    await eventually(lambda: frames)
    assert frames == [b"\xff\xd8 a jpeg"]

    await remote.handle(TakeoverText(type="text", text="typed on the API side"))
    await eventually(lambda: stub.sessions[run_id].inputs)
    assert stub.sessions[run_id].inputs[0].text == "typed on the API side"

    with pytest.raises(TakeoverError) as again:
        await api.start(run_id, on_frame, on_blocked, on_end)
    assert again.value.reason == "active"

    assert await api.hand_back(run_id, 3, "step") is True
    assert await api.hand_back(run_id, 9, "step") is False
    assert stub.handbacks[-2:] == [(run_id, 3, "step"), (run_id, 9, "step")]

    await remote.end("closed")
    await eventually(lambda: ended)
    assert ended == ["closed"] and remote.ended == "closed" and api.takeover(run_id) is None
