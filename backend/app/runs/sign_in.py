"""Who is signed in, on any site (ADR 0012, #476): no per-site code.

When the owner hands back a sign-in takeover, Krama compares the browser's cookies with those it had when
the sign-in page opened. A new session-like cookie (named for a session, auth, token, sid, login, user,
remember or jwt) and no visible password field mean the owner is signed in. The account is shown as "your
account on <host>": the page's own account name isn't reliable enough to read on an unknown site.
"""

import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from playwright.async_api import Page

from app.agent.stored_session import StorageState

AccountOf = Callable[[Page, StorageState], Awaitable[str | None]]

_SESSION_LIKE = re.compile(r"sess|auth|token|sid|login|user|remember|jwt|account|identity", re.IGNORECASE)


def cookie_names(state: Mapping[str, Any]) -> set[str]:
    cookies = state.get("cookies") or []
    return {str(c["name"]) for c in cookies if isinstance(c, Mapping) and c.get("name")}


def new_session_cookies(before: set[str], state: Mapping[str, Any]) -> list[str]:
    """Session-like cookies that weren't there before the sign-in."""
    return sorted(n for n in cookie_names(state) - before if _SESSION_LIKE.search(n))


def generic_account_of(before: set[str], host: str) -> AccountOf:
    """An `account_of` for any site: signed in once a new session-like cookie exists and no password field is
    visible on the page."""

    async def account_of(page: Page, state: StorageState) -> str | None:
        if not new_session_cookies(before, state):
            return None
        if await page.locator("input[type=password]").filter(visible=True).count():
            return None  # still on a sign-in form (a second step, or a wrong password)
        return f"your account on {host}"

    return account_of
