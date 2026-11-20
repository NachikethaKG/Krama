"""Human takeover across processes (#413, ADR 0008 T13): the browser lives in the arq worker, the screen
WebSocket in the API.

Redis pub/sub carries it, like the rest of the API ↔ worker traffic (app/runs/queue.py):
- `krama:takeover:control`: API → worker requests {action: start | handback | end, run_id, req, ...};
- `krama:takeover:<run>:reply`: the worker's answer to a start or handback request {req, ok, reason?, ...};
- `krama:takeover:<run>:out`: worker → API, JPEG frames (bytes) and notices (JSON: blocked, ended);
- `krama:takeover:<run>:in`: API → worker, the owner's input (`TakeoverInput` JSON).

The worker's session caps frames at 15 per second before they reach Redis. Frames are never stored.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter, ValidationError

from app.contracts_gen.takeover_schema import TakeoverInput as TakeoverInputModel
from app.runs.takeover import FrameSink, Notice, TakeoverError, TakeoverInput

logger = logging.getLogger(__name__)

CONTROL = "krama:takeover:control"
_INPUT: TypeAdapter[Any] = TypeAdapter(TakeoverInputModel)
REPLY_TIMEOUT_S = 15.0


def reply_channel(run_id: UUID) -> str:
    return f"krama:takeover:{run_id}:reply"


def out_channel(run_id: UUID) -> str:
    return f"krama:takeover:{run_id}:out"


def in_channel(run_id: UUID) -> str:
    return f"krama:takeover:{run_id}:in"


class RemoteTakeover:
    """The API's handle on a takeover running in the worker: the same surface as `TakeoverSession`."""

    def __init__(self, redis: Any, run_id: UUID, step_seq: int) -> None:
        self._redis = redis
        self.run_id = run_id
        self.step_seq = step_seq
        self.started_wall = datetime.now(UTC)
        self.last_input_wall: datetime | None = None
        self.ended: str | None = None
        self.reader: asyncio.Task[None] | None = None

    async def handle(self, message: TakeoverInput) -> None:
        if self.ended is not None:
            return
        self.last_input_wall = datetime.now(UTC)
        await self._redis.publish(in_channel(self.run_id), message.model_dump_json(exclude_none=True))

    async def end(self, reason: str) -> None:
        if self.ended is not None:
            return
        await self._redis.publish(
            CONTROL, json.dumps({"action": "end", "run_id": str(self.run_id), "reason": reason})
        )


class ApiTakeoverRelay:
    """API side: asks the worker to start, hand back or end a takeover, and relays its frames and notices."""

    def __init__(self, redis_factory: Callable[[], Awaitable[Any]]) -> None:
        self._redis_factory = redis_factory
        self._active: dict[UUID, RemoteTakeover] = {}

    def takeover(self, run_id: UUID) -> RemoteTakeover | None:
        return self._active.get(run_id)

    async def start(
        self, run_id: UUID, on_frame: FrameSink, on_blocked: Notice | None, on_end: Notice | None
    ) -> RemoteTakeover:
        redis = await self._redis_factory()
        pubsub = redis.pubsub()
        await pubsub.subscribe(out_channel(run_id))
        reply = await self._request(redis, run_id, {"action": "start"})
        if not reply.get("ok"):
            await pubsub.aclose()
            raise TakeoverError(
                reply.get("reason", "not_available"), reply.get("message", "No takeover possible")
            )
        remote = RemoteTakeover(redis, run_id, int(reply["step_seq"]))
        self._active[run_id] = remote

        async def read() -> None:
            try:
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    data = message["data"]
                    if data[:1] != b"{":
                        await on_frame(data)
                        continue
                    notice = json.loads(data)
                    if notice.get("type") == "blocked" and on_blocked is not None:
                        await on_blocked(notice.get("message", ""))
                    elif notice.get("type") == "ended":
                        remote.ended = notice.get("reason", "closed")
                        self._active.pop(run_id, None)
                        if on_end is not None:
                            await on_end(remote.ended)
                        return
            finally:
                await pubsub.aclose()

        remote.reader = asyncio.create_task(read(), name=f"takeover-relay-{run_id}")
        return remote

    async def hand_back(self, run_id: UUID, step_seq: int, done: str) -> bool:
        redis = await self._redis_factory()
        reply = await self._request(redis, run_id, {"action": "handback", "step_seq": step_seq, "done": done})
        return bool(reply.get("ok"))

    async def _request(self, redis: Any, run_id: UUID, body: dict[str, Any]) -> dict[str, Any]:
        req = uuid.uuid4().hex
        pubsub = redis.pubsub()
        await pubsub.subscribe(reply_channel(run_id))
        try:
            await redis.publish(CONTROL, json.dumps({**body, "run_id": str(run_id), "req": req}))
            async with asyncio.timeout(REPLY_TIMEOUT_S):
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    answer: dict[str, Any] = json.loads(message["data"])
                    if answer.get("req") == req:
                        return answer
        except TimeoutError:
            return {"ok": False, "reason": "not_available", "message": "The worker didn't answer"}
        finally:
            await pubsub.aclose()
        return {"ok": False, "reason": "not_available"}


class WorkerTakeoverRelay:
    """Worker side: serves the API's takeover requests with the worker's own `InProcessExecutor`."""

    def __init__(self, redis_url: str, executor: Any) -> None:
        self._url = redis_url
        self._executor = executor
        self._inputs: dict[UUID, asyncio.Task[None]] = {}

    async def run(self) -> None:
        from redis.asyncio import Redis

        while True:
            try:
                async with Redis.from_url(self._url) as redis, redis.pubsub() as pubsub:
                    await pubsub.subscribe(CONTROL)
                    async for message in pubsub.listen():
                        if message.get("type") == "message":
                            await self._serve(redis, message["data"])
            except asyncio.CancelledError:
                for task in self._inputs.values():
                    task.cancel()
                raise
            except Exception:
                logger.warning("worker lost Redis for takeovers, retrying in 2 s", exc_info=True)
                await asyncio.sleep(2)

    async def _serve(self, redis: Any, raw: bytes) -> None:
        try:
            request = json.loads(raw)
            run_id = UUID(request["run_id"])
        except (ValueError, KeyError, TypeError):
            return
        action, req = request.get("action"), request.get("req")
        if action == "end":
            await self._executor.end_takeover(run_id, request.get("reason", "closed"))
            return
        if action == "handback":
            ok = await self._executor.hand_back(run_id, int(request["step_seq"]), str(request["done"]))
            await redis.publish(reply_channel(run_id), json.dumps({"req": req, "ok": ok}))
            return
        if action != "start":
            return

        async def frame(data: bytes) -> None:
            await redis.publish(out_channel(run_id), data)

        async def blocked(message: str) -> None:
            await redis.publish(out_channel(run_id), json.dumps({"type": "blocked", "message": message}))

        async def ended(reason: str) -> None:
            task = self._inputs.pop(run_id, None)
            if task is not None and task is not asyncio.current_task():
                task.cancel()
            await redis.publish(out_channel(run_id), json.dumps({"type": "ended", "reason": reason}))

        try:
            session = await self._executor.start_takeover(run_id, frame, on_blocked=blocked, on_end=ended)
        except TakeoverError as e:
            answer = {"req": req, "ok": False, "reason": e.reason, "message": str(e)}
            await redis.publish(reply_channel(run_id), json.dumps(answer))
            return
        self._inputs[run_id] = asyncio.create_task(self._relay_input(run_id, session))
        await redis.publish(
            reply_channel(run_id), json.dumps({"req": req, "ok": True, "step_seq": session.step_seq})
        )

    async def _relay_input(self, run_id: UUID, session: Any) -> None:
        from redis.asyncio import Redis

        async with Redis.from_url(self._url) as redis, redis.pubsub() as pubsub:
            await pubsub.subscribe(in_channel(run_id))
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                with contextlib.suppress(ValidationError):
                    await session.handle(_INPUT.validate_json(message["data"]))
                if session.ended is not None:
                    return
