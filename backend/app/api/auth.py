"""POST /auth/login, POST /auth/logout, GET /auth/me, and `CurrentUser`, the dependency every other route uses
(docs/api-contract.md; #94). The session lives in an HTTP-only cookie, never in a response body."""

import time
from collections import defaultdict, deque
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response

from app.api.accounts import (
    LoginThrottledError,
    SessionLimits,
    authenticate,
    end_session,
    session_user,
    start_session,
)
from app.api.errors import ApiException
from app.api.services import ServicesDep
from app.config import Settings, get_settings
from app.contracts_gen.auth_schema import LoginRequest, User
from app.contracts_gen.common_schema import ErrorResponse
from app.db import UserRow

type Responses = dict[int | str, dict[str, Any]]

router = APIRouter(tags=["auth"])
_401: Responses = {401: {"model": ErrorResponse, "description": "Not signed in"}}
WRONG_LOGIN = "Wrong email or password"

IP_ATTEMPTS = 20
IP_WINDOW_S = 600.0
_attempts: defaultdict[str, deque[float]] = defaultdict(deque)
"""Sign-in attempts per client IP in the last IP_WINDOW_S (one API process, so memory is enough)."""


def session_limits(settings: Settings) -> SessionLimits:
    return SessionLimits(idle=settings.session_idle, absolute=settings.session_absolute)


async def current_user(request: Request, services: ServicesDep) -> UserRow:
    """The signed-in user, else 401. Use it as `user: CurrentUser` on every route that isn't public."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        async with services.sessions.begin() as s:
            user = await session_user(s, token, session_limits(settings))
        if user is not None:
            return user
    raise ApiException(401, "unauthorized", "Sign in first")


CurrentUser = Annotated[UserRow, Depends(current_user)]


def user_out(user: UserRow) -> User:
    return User(id=user.id, email=user.email, display_name=user.display_name, created_at=user.created_at)


@router.post(
    "/auth/login",
    responses={
        401: {"model": ErrorResponse, "description": WRONG_LOGIN},
        429: {"model": ErrorResponse, "description": "Too many failed sign-ins; wait and retry"},
    },
)
async def login(body: LoginRequest, request: Request, response: Response, services: ServicesDep) -> User:
    """Signs in and sets the session cookie. Any session the browser had before is replaced."""
    settings = get_settings()
    _count_attempt(request.client.host if request.client else "unknown")
    async with services.sessions.begin() as s:
        try:
            user = await authenticate(s, body.email, body.password)
        except LoginThrottledError as e:
            raise ApiException(
                429, "rate_limited", "Too many failed sign-ins", {"retry_after_s": e.retry_after_s}
            ) from None
        if user is None:
            failed = True
        else:
            failed = False
            old = request.cookies.get(settings.session_cookie_name)
            if old:
                await end_session(s, old)
            token = await start_session(s, user, session_limits(settings))
    if failed:  # the failure counter above is committed, then the generic answer
        raise ApiException(401, "unauthorized", WRONG_LOGIN)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=int(settings.session_absolute.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )
    assert user is not None
    return user_out(user)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, services: ServicesDep) -> None:
    """Revokes the session on the server and clears the cookie (also fine when already signed out)."""
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        async with services.sessions.begin() as s:
            await end_session(s, token)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


@router.get("/auth/me", responses=_401)
async def me(user: CurrentUser) -> User:
    return user_out(user)


def _count_attempt(ip: str) -> None:
    now = time.monotonic()
    recent = _attempts[ip]
    while recent and now - recent[0] > IP_WINDOW_S:
        recent.popleft()
    if len(recent) >= IP_ATTEMPTS:
        retry = int(IP_WINDOW_S - (now - recent[0])) + 1
        raise ApiException(429, "rate_limited", "Too many sign-in attempts", {"retry_after_s": retry})
    recent.append(now)
