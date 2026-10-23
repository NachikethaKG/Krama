"""Signed-in browser sessions for real sites (#87): log in once by hand, reuse the encrypted session after.

A human signs in once in a headed browser (password and 2FA typed by them, never seen by Krama). Krama keeps
Playwright's `storage_state` (cookies + localStorage), encrypted with Fernet, and opens later runs with it.
Before a run it checks the session cookie's expiry; after the first page load it checks the page really shows
a signed-in user. Either failing stops the run with "log in again" (docs/research/phase-3-vishwas-logged-in-
sessions.md).

The state is a secret: it is only ever written encrypted, never logged, and never put in an artifact.
"""

import asyncio
import json
import os
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

type StorageState = dict[str, Any]
"""Playwright's `BrowserContext.storage_state()`: {"cookies": [...], "origins": [...]}."""
type SignedInCheck = Callable[[Page], Awaitable[bool]]


class SessionVaultError(RuntimeError):
    """A stored session exists but can't be read (wrong or missing key, damaged file)."""


@dataclass(frozen=True)
class SiteLogin:
    """How one site keeps a user signed in, and how to see that it does."""

    site: str
    login_path: str
    session_cookie: str
    """Its expiry is the session's (GitHub: `user_session`, two weeks)."""
    probe_path: str
    """A page only a signed-in user can open (a signed-out user is sent to the login page)."""
    signed_in_check: SignedInCheck


async def github_signed_in(page: Page) -> bool:
    """GitHub names the signed-in user in `<meta name="user-login">`; signed out it is empty."""
    login = await page.locator('meta[name="user-login"]').first.get_attribute("content", timeout=2_000)
    return bool(login and login.strip())


GITHUB = SiteLogin(
    site="github",
    login_path="/login",
    session_cookie="user_session",
    probe_path="/settings/profile",
    signed_in_check=github_signed_in,
)
SITES = {GITHUB.site: GITHUB}


class SessionVault:
    """Encrypted storage states, one file per site. `keys`: Fernet keys, newest first, comma-separated; the
    newest encrypts, any of them decrypts (so a key can be rotated)."""

    def __init__(self, directory: Path, keys: str) -> None:
        self._dir = directory
        parsed = [k.strip() for k in keys.split(",") if k.strip()]
        try:
            self._fernet = MultiFernet([Fernet(k) for k in parsed]) if parsed else None
        except ValueError as e:
            raise SessionVaultError("KRAMA_STORAGE_KEY is not a valid Fernet key") from e

    def _path(self, site: str) -> Path:
        if not site.isidentifier():
            raise ValueError(f"bad site name {site!r}")
        return self._dir / f"{site}.session"

    def _require_key(self) -> MultiFernet:
        if self._fernet is None:
            raise SessionVaultError("KRAMA_STORAGE_KEY is not set (create one with `krama session key`)")
        return self._fernet

    def save(self, site: str, state: StorageState) -> Path:
        token = self._require_key().encrypt(json.dumps(state).encode("utf-8"))
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(site)
        # Write to a temp file, then rename: a crash never leaves half a session behind.
        fd, tmp = tempfile.mkstemp(dir=self._dir, prefix=f".{site}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(token)
        os.replace(tmp, path)
        return path

    def load(self, site: str) -> StorageState | None:
        """The stored state, or None if there is none."""
        path = self._path(site)
        if not path.exists():
            return None
        try:
            state: StorageState = json.loads(self._require_key().decrypt(path.read_bytes()))
        except InvalidToken as e:
            message = f"the stored {site} session can't be decrypted with KRAMA_STORAGE_KEY"
            raise SessionVaultError(message) from e
        return state

    def delete(self, site: str) -> bool:
        path = self._path(site)
        existed = path.exists()
        path.unlink(missing_ok=True)
        return existed


def new_key() -> str:
    return Fernet.generate_key().decode()


def cookie_expiry(state: StorageState, name: str) -> datetime | None:
    """When the cookie `name` expires, or None if it is missing or lasts only the browser session (-1)."""
    for cookie in state.get("cookies", []):
        if cookie.get("name") == name and float(cookie.get("expires", -1)) > 0:
            return datetime.fromtimestamp(float(cookie["expires"]), UTC)
    return None


def sign_in_problem(state: StorageState | None, login: SiteLogin, now: datetime | None = None) -> str | None:
    """Why this stored session can't be used, or None if it still looks valid. Cheap: no browser."""
    if state is None:
        return f"No stored {login.site} session. Log in once with `krama session capture {login.site}`."
    expires = cookie_expiry(state, login.session_cookie)
    if expires is None:
        return f"The stored {login.site} session has no sign-in cookie. Log in again."
    if expires <= (now or datetime.now(UTC)):
        return f"The stored {login.site} session expired on {expires:%Y-%m-%d}. Log in again."
    return None


async def capture(login: SiteLogin, base_url: str, vault: SessionVault, *, timeout_s: float = 600.0,
                  headless: bool = False) -> datetime | None:  # fmt: skip
    """Open the site's login page in a visible browser, wait until the human has signed in, store the session.
    Returns when the session cookie expires. The human types the password and any 2FA code; Krama only waits
    for the signed-in page and never reads a form field."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(base_url=base_url)
            page = await context.new_page()
            await page.goto(login.login_path, wait_until="domcontentloaded")
            async with asyncio.timeout(timeout_s):
                # Polling the page: the human signs in at their own pace, with no event to wait for.
                while not await _signed_in(page, login):  # noqa: ASYNC110
                    await asyncio.sleep(1.0)
            state = cast(StorageState, await context.storage_state())
        finally:
            await browser.close()
    vault.save(login.site, state)
    return cookie_expiry(state, login.session_cookie)


async def probe(login: SiteLogin, base_url: str, state: StorageState) -> bool:
    """Open the signed-in-only page headlessly with the stored session: still signed in?"""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            context = await browser.new_context(base_url=base_url, storage_state=state)  # type: ignore[arg-type]
            page = await context.new_page()
            await page.goto(login.probe_path, wait_until="domcontentloaded")
            return not _on_login_page(page, login) and await login.signed_in_check(page)
        finally:
            await browser.close()


async def _signed_in(page: Page, login: SiteLogin) -> bool:
    try:
        return not _on_login_page(page, login) and await login.signed_in_check(page)
    except PlaywrightError:  # the page is mid-navigation while the human signs in
        return False


def _on_login_page(page: Page, login: SiteLogin) -> bool:
    path = page.url.split("://", 1)[-1].partition("/")[2]
    return ("/" + path).startswith((login.login_path, "/session"))
