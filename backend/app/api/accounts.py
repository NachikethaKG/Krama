"""Accounts and sign-in sessions (#94; docs/research/phase-3-vishwas-accounts-and-csrf.md).

- Passwords: argon2id with argon2-cffi's defaults (RFC 9106 low-memory: t=3, m=64 MiB, p=4), at least 15
  characters (NIST SP 800-63B rev 4 for a single factor), rehashed when the parameters change.
- Sessions: an opaque 256-bit token in an HTTP-only cookie; the database keeps only its SHA-256, so a leaked
  table signs nobody in. Idle and absolute limits are checked on every request; logout revokes server-side.
- Brute force: one generic answer for a wrong email or password, a password check even for unknown emails (no
  timing difference), and a doubling wait per account after a few failures in a row.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionRow, UserRow

MIN_PASSWORD = 15
MAX_PASSWORD = 128
FREE_FAILURES = 5
"""Failed sign-ins in a row before each further one doubles the wait (1 s, 2 s, 4 s, … up to MAX_WAIT)."""
MAX_WAIT = timedelta(minutes=15)
LAST_SEEN_EVERY = timedelta(minutes=5)
"""last_seen_at is written at most this often, not on every request."""

_hasher = PasswordHasher()
# Verified against when the email is unknown, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


class PasswordRuleError(ValueError):
    pass


class LoginThrottledError(Exception):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"too many failed sign-ins, retry in {retry_after_s} s")
        self.retry_after_s = retry_after_s


@dataclass(frozen=True)
class SessionLimits:
    idle: timedelta = timedelta(days=7)
    absolute: timedelta = timedelta(days=30)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        raise PasswordRuleError(f"a password needs {MIN_PASSWORD} to {MAX_PASSWORD} characters")
    return _hasher.hash(password)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_user(s: AsyncSession, email: str, password: str, display_name: str | None = None) -> UserRow:
    user = UserRow(
        email=normalize_email(email), password_hash=hash_password(password), display_name=display_name
    )
    s.add(user)
    await s.flush()
    return user


async def authenticate(
    s: AsyncSession, email: str, password: str, now: datetime | None = None
) -> UserRow | None:
    """The user if the email and password match, else None. Raises LoginThrottledError while the account
    waits after repeated failures (checked before the password, so guessing during the wait gains nothing)."""
    now = now or datetime.now(UTC)
    user = await s.scalar(select(UserRow).where(UserRow.email == normalize_email(email)).with_for_update())
    if user is not None:
        wait = _wait_after(user.failed_logins)
        if user.last_failed_at is not None and now < user.last_failed_at + wait:
            raise LoginThrottledError(max(1, int((user.last_failed_at + wait - now).total_seconds()) + 1))
    try:
        _hasher.verify(user.password_hash if user else _DUMMY_HASH, password)
        ok = user is not None
    except (VerificationError, InvalidHashError):
        ok = False
    if user is None:
        return None
    if not ok:
        user.failed_logins += 1
        user.last_failed_at = now
        return None
    user.failed_logins, user.last_failed_at = 0, None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    return user


def _wait_after(failures: int) -> timedelta:
    if failures < FREE_FAILURES:
        return timedelta(0)
    return min(timedelta(seconds=2 ** (failures - FREE_FAILURES)), MAX_WAIT)


async def start_session(
    s: AsyncSession, user: UserRow, limits: SessionLimits, now: datetime | None = None
) -> str:
    """A new session for `user`; returns the token for the cookie (only its hash is stored)."""
    now = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    s.add(
        SessionRow(
            user_id=user.id, token_hash=token_hash(token), last_seen_at=now, expires_at=now + limits.absolute
        )
    )
    await s.flush()
    return token


async def session_user(
    s: AsyncSession, token: str, limits: SessionLimits, now: datetime | None = None
) -> UserRow | None:
    """The signed-in user for a cookie token, or None (unknown, revoked, idle too long or past its limit)."""
    now = now or datetime.now(UTC)
    row = await s.scalar(select(SessionRow).where(SessionRow.token_hash == token_hash(token)))
    if (
        row is None
        or row.revoked_at is not None
        or now >= row.expires_at
        or now >= row.last_seen_at + limits.idle
    ):
        return None
    if now - row.last_seen_at >= LAST_SEEN_EVERY:
        row.last_seen_at = now
    return await s.get(UserRow, row.user_id)


async def end_session(s: AsyncSession, token: str, now: datetime | None = None) -> None:
    await s.execute(
        update(SessionRow)
        .where(SessionRow.token_hash == token_hash(token), SessionRow.revoked_at.is_(None))
        .values(revoked_at=now or datetime.now(UTC))
    )


async def end_all_sessions(s: AsyncSession, user_id: UUID, now: datetime | None = None) -> None:
    """Sign a user out everywhere (e.g. after a password change)."""
    await s.execute(
        update(SessionRow)
        .where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=now or datetime.now(UTC))
    )
