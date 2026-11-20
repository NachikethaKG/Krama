"""Human takeover (#408, ADR 0008): POST /runs/{id}/takeover, POST /runs/{id}/handback, WS /runs/{id}/screen.

The owner of a paused run takes control of its live page: `takeover` starts the session, the screen
WebSocket streams its frames (binary JPEG) and carries the owner's input (`TakeoverInput` JSON), `handback`
ends it and says what was done. The WebSocket checks the session cookie, the `Origin` and the run's owner
itself: the CSRF middleware only covers HTTP requests. Frames are never stored.
"""

import asyncio
import contextlib
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from app.api.accounts import session_user
from app.api.auth import CurrentUser, session_limits
from app.api.errors import ApiException
from app.api.owner import owned_run, run_owner
from app.api.runs import _run_out
from app.api.services import Services, ServicesDep
from app.config import get_settings
from app.contracts_gen.common_schema import ErrorResponse
from app.contracts_gen.run_schema import Run, RunHandBackRequest
from app.contracts_gen.takeover_schema import TakeoverInput, TakeoverServerMessage
from app.runs.takeover import HEIGHT, WIDTH, ScreenFeed, TakeoverError

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runs"])
_INPUT: TypeAdapter[Any] = TypeAdapter(TakeoverInput)
_404: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse, "description": "No run with this id"}}

CLOSE_FORBIDDEN = 4403
"""Not signed in, an unknown origin, or not the run's owner."""
CLOSE_TAKEN = 4409
"""No active takeover, or someone else already watches it."""


@router.post(
    "/runs/{run_id}/takeover",
    responses={
        **_404,
        409: {"model": ErrorResponse, "description": "No takeover possible, or one is active"},
    },
)
async def start_takeover(run_id: UUID, user: CurrentUser, services: ServicesDep) -> Run:
    """Take control of the paused run's page (ADR 0008). The run stays paused; open WS /runs/{id}/screen."""
    async with services.sessions() as s:
        await owned_run(s, run_id, user)
    feed = ScreenFeed()
    try:
        await services.executor.start_takeover(run_id, feed.frame, on_blocked=feed.blocked, on_end=feed.ended)
    except TakeoverError as e:
        if e.reason == "active":
            raise ApiException(409, "conflict", str(e), {"reason": "takeover_active"}) from None
        raise ApiException(409, "run_not_active", str(e)) from None
    services.screens[run_id] = feed
    async with services.sessions() as s:
        return await _run_out(s, run_id, user, services)


@router.post(
    "/runs/{run_id}/handback",
    responses={**_404, 409: {"model": ErrorResponse, "description": "No active takeover at this step"}},
)
async def hand_back(run_id: UUID, body: RunHandBackRequest, user: CurrentUser, services: ServicesDep) -> Run:
    """End the takeover and say what was done: Krama checks it and continues, or pauses again."""
    async with services.sessions() as s:
        await owned_run(s, run_id, user)
    if not await services.executor.hand_back(run_id, body.step_seq, body.done):
        raise ApiException(409, "run_not_active", f"No active takeover at step {body.step_seq}")
    async with services.sessions() as s:
        return await _run_out(s, run_id, user, services)


@router.websocket("/runs/{run_id}/screen")
async def screen(websocket: WebSocket, run_id: UUID) -> None:
    services: Services = websocket.app.state.services
    if not await _allowed(websocket, services, run_id):
        await websocket.close(code=CLOSE_FORBIDDEN)
        return
    feed = services.screens.get(run_id)
    session = services.executor.takeover(run_id)
    if feed is None or session is None or not feed.attach():
        await websocket.close(code=CLOSE_TAKEN)
        return
    await websocket.accept()
    await websocket.send_text(_message("ready", width=WIDTH, height=HEIGHT))
    sender = asyncio.create_task(_send(websocket, feed))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = _INPUT.validate_json(raw)
            except ValidationError:
                await websocket.send_text(_message("blocked", message="That input isn't understood."))
                continue
            await session.handle(message)
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender
        feed.detach()
        if session.ended is None:
            await session.end("closed")  # the viewer went away: the run stays paused
        services.screens.pop(run_id, None)


async def _send(websocket: WebSocket, feed: ScreenFeed) -> None:
    while True:
        item = await feed.next()
        if isinstance(item, bytes):
            await websocket.send_bytes(item)
            continue
        await websocket.send_text(json.dumps(item))
        if item.get("type") == "ended":
            await websocket.close()
            return


async def _allowed(websocket: WebSocket, services: Services, run_id: UUID) -> bool:
    settings = get_settings()
    origin = (websocket.headers.get("origin") or "").rstrip("/")
    if origin not in {o.rstrip("/") for o in settings.cors_origins}:
        return False
    token = websocket.cookies.get(settings.session_cookie_name)
    if not token:
        return False
    async with services.sessions.begin() as s:
        user = await session_user(s, token, session_limits(settings))
        owner = await run_owner(s, run_id) if user is not None else None
    return user is not None and owner == user.id


def _message(kind: str, **fields: Any) -> str:
    return TakeoverServerMessage.model_validate({"type": kind, **fields}).model_dump_json(exclude_none=True)
