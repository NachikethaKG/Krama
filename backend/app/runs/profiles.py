"""Per-user site sessions (#404, ADR 0007): each Krama user's own signed-in browser session per site.

The Playwright `storage_state` is a secret as strong as a password: it is encrypted with `KRAMA_STORAGE_KEY`
(Fernet, newest key first so keys can rotate), decrypted only inside the run that uses it, and never logged,
returned by the API or sent to an LLM.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.stored_session import StorageState, cookie_expiry
from app.db import BrowserProfileRow


class ProfileError(Exception):
    """The store can't encrypt or decrypt (no key, or a key that doesn't fit)."""


@dataclass(frozen=True)
class Profile:
    site: str
    account: str
    state: StorageState
    captured_at: datetime
    expires_at: datetime | None
    sign_in_hosts: tuple[str, ...] = ()


class ProfileStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], keys: str) -> None:
        self._sessions = sessions
        parsed = [k.strip() for k in keys.split(",") if k.strip()]
        try:
            self._fernet = MultiFernet([Fernet(k) for k in parsed]) if parsed else None
        except ValueError as e:
            raise ProfileError("KRAMA_STORAGE_KEY is not a valid Fernet key") from e

    def _key(self) -> MultiFernet:
        if self._fernet is None:
            raise ProfileError("KRAMA_STORAGE_KEY is not set (create one with `krama session key`)")
        return self._fernet

    async def save(
        self,
        user_id: UUID,
        site: str,
        account: str,
        state: StorageState,
        *,
        session_cookie: str | None = None,
        sign_in_hosts: Iterable[str] = (),
    ) -> None:
        """Store (or replace) the user's session on `site`, with the other hosts its sign-in used."""
        token = self._key().encrypt(json.dumps(state).encode("utf-8"))
        expires = cookie_expiry(state, session_cookie) if session_cookie else None
        async with self._sessions.begin() as s:
            row = await s.scalar(
                select(BrowserProfileRow).where(
                    BrowserProfileRow.user_id == user_id, BrowserProfileRow.site == site
                )
            )
            if row is None:
                row = BrowserProfileRow(user_id=user_id, site=site, account=account, state=token)
                s.add(row)
            row.account, row.state = account, token
            row.captured_at, row.expires_at = datetime.now(UTC), expires
            row.sign_in_hosts = sorted({h.lower() for h in sign_in_hosts if h})

    async def load(self, user_id: UUID, site: str) -> Profile | None:
        """The user's session on `site`, or None (none stored, expired, or unreadable with the current
        keys)."""
        async with self._sessions() as s:
            row = await s.scalar(
                select(BrowserProfileRow).where(
                    BrowserProfileRow.user_id == user_id, BrowserProfileRow.site == site
                )
            )
        if row is None or (row.expires_at is not None and row.expires_at <= datetime.now(UTC)):
            return None
        try:
            state: StorageState = json.loads(self._key().decrypt(row.state))
        except (InvalidToken, ProfileError):
            return None
        hosts = tuple(row.sign_in_hosts or ())
        return Profile(row.site, row.account, state, row.captured_at, row.expires_at, hosts)

    async def list(self, user_id: UUID) -> list[BrowserProfileRow]:
        """The user's stored sessions (rows only: callers never get the decrypted state)."""
        async with self._sessions() as s:
            rows = await s.scalars(
                select(BrowserProfileRow)
                .where(BrowserProfileRow.user_id == user_id)
                .order_by(BrowserProfileRow.site)
            )
            return list(rows)

    async def delete(self, user_id: UUID, site: str) -> bool:
        async with self._sessions.begin() as s:
            done = await s.execute(
                delete(BrowserProfileRow).where(
                    BrowserProfileRow.user_id == user_id, BrowserProfileRow.site == site
                )
            )
        return bool(getattr(done, "rowcount", 0))
