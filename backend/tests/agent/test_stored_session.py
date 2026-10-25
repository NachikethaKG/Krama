"""Stored signed-in sessions (#87): encrypted at rest, expiry detected, a dead session caught at once.

A tiny local site plays GitHub: `/login` signs in by itself after a moment (standing in for the human), and
pages show `<meta name="user-login">` only when the session cookie comes back.
"""

import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.agent import PlaywrightSession, SessionConfig
from app.agent.stored_session import (
    SessionVault,
    SessionVaultError,
    SiteLogin,
    StorageState,
    capture,
    cookie_expiry,
    github_signed_in,
    new_key,
    probe,
    sign_in_problem,
)
from app.config import Settings
from app.targets import target_setup

pytestmark = pytest.mark.anyio

SECRET = "s3ssion-cookie-value"
LOGIN = SiteLogin(
    site="github",
    login_path="/login",
    session_cookie="user_session",
    probe_path="/settings/profile",
    signed_in_check=github_signed_in,
)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        signed_in = f"user_session={SECRET}" in (self.headers.get("Cookie") or "")
        if self.path == "/login":  # the "human" signs in after a moment
            self._page('<script>setTimeout(() => { location.href = "/signed-in" }, 400)</script>', user="")
        elif self.path == "/signed-in":
            expires = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + 14 * 86400))
            self._redirect("/", cookie=f"user_session={SECRET}; Path=/; HttpOnly; Expires={expires}")
        elif self.path == "/settings/profile" and not signed_in:
            self._redirect("/login?return_to=/settings/profile")
        else:
            self._page("<h1>Home</h1>", user="krama-bot" if signed_in else "")

    def _page(self, body: str, *, user: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            f'<!doctype html><meta name="user-login" content="{user}"><title>T</title>{body}'.encode()
        )

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(302)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Location", location)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def fake_github() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def state(expires_in: timedelta | None = timedelta(days=14), value: str = SECRET) -> StorageState:
    expires = (datetime.now(UTC) + expires_in).timestamp() if expires_in is not None else -1
    cookie = {"name": "user_session", "value": value, "domain": "127.0.0.1", "path": "/", "expires": expires,
              "httpOnly": True, "secure": False, "sameSite": "Lax"}  # fmt: skip
    return {"cookies": [cookie], "origins": []}


# --- the vault ---


def test_the_session_is_encrypted_on_disk(tmp_path: Path) -> None:
    vault = SessionVault(tmp_path, new_key())

    path = vault.save("github", state())

    assert SECRET.encode() not in path.read_bytes()
    loaded = vault.load("github")
    assert loaded is not None and loaded["cookies"][0]["value"] == SECRET


def test_a_wrong_key_cannot_read_it(tmp_path: Path) -> None:
    SessionVault(tmp_path, new_key()).save("github", state())

    with pytest.raises(SessionVaultError, match="can't be decrypted"):
        SessionVault(tmp_path, new_key()).load("github")


def test_no_key_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(SessionVaultError, match="KRAMA_STORAGE_KEY is not set"):
        SessionVault(tmp_path, "").save("github", state())


def test_an_old_key_still_reads_after_a_rotation(tmp_path: Path) -> None:
    old, new = new_key(), new_key()
    SessionVault(tmp_path, old).save("github", state())

    assert SessionVault(tmp_path, f"{new},{old}").load("github") is not None


def test_a_missing_session_is_none(tmp_path: Path) -> None:
    assert SessionVault(tmp_path, new_key()).load("github") is None


# --- expiry ---


def test_expiry_comes_from_the_session_cookie() -> None:
    expires = cookie_expiry(state(timedelta(days=3)), "user_session")

    assert expires is not None and timedelta(days=2) < expires - datetime.now(UTC) < timedelta(days=4)
    assert cookie_expiry(state(None), "user_session") is None  # a browser-session cookie


@pytest.mark.parametrize(
    ("stored", "problem"),
    [
        (None, "No stored github session"),
        (state(timedelta(days=-1)), "expired"),
        (state(None), "no sign-in cookie"),
        (state(), None),
    ],
)
def test_sign_in_problem(stored: StorageState | None, problem: str | None) -> None:
    found = sign_in_problem(stored, LOGIN)

    assert found is None if problem is None else (found is not None and problem in found)


# --- capture and probe in a real browser ---


async def test_capture_waits_for_the_sign_in_and_stores_the_session(fake_github: str, tmp_path: Path) -> None:
    vault = SessionVault(tmp_path, new_key())

    expires = await capture(LOGIN, fake_github, vault, timeout_s=20, headless=True)

    assert expires is not None and expires > datetime.now(UTC) + timedelta(days=13)
    stored = vault.load("github")
    assert stored is not None and any(c["value"] == SECRET for c in stored["cookies"])
    assert SECRET.encode() not in (tmp_path / "github.session").read_bytes()


async def test_capture_gives_up_when_nobody_signs_in(fake_github: str, tmp_path: Path) -> None:
    never = SiteLogin("github", "/settings/profile", "user_session", "/", github_signed_in)  # never signs in

    with pytest.raises(TimeoutError):
        await capture(never, fake_github, SessionVault(tmp_path, new_key()), timeout_s=2, headless=True)


async def test_probe_tells_a_live_session_from_a_dead_one(fake_github: str) -> None:
    assert await probe(LOGIN, fake_github, state()) is True
    assert await probe(LOGIN, fake_github, state(value="revoked")) is False


async def test_a_browser_session_opens_with_the_stored_state(fake_github: str) -> None:
    config = SessionConfig(base_url=fake_github, storage_state=state())

    async with PlaywrightSession(config) as session:
        await session.page.goto("/")
        assert await github_signed_in(session.page)


# --- the GitHub target ---


def settings(tmp_path: Path, key: str) -> Settings:
    return Settings(sessions_dir=tmp_path, krama_storage_key=key, github_test_user="krama-bot")


def test_github_without_a_stored_session_says_to_log_in(tmp_path: Path) -> None:
    setup = target_setup("https://github.com", settings(tmp_path, new_key()))

    assert setup.site == "github" and setup.storage_state is None
    assert setup.sign_in_problem is not None and "krama session capture github" in setup.sign_in_problem


def test_github_with_a_valid_session_opens_signed_in(tmp_path: Path) -> None:
    key = new_key()
    SessionVault(tmp_path, key).save("github", state())

    setup = target_setup("https://github.com/", settings(tmp_path, key))

    assert setup.sign_in_problem is None and setup.signed_in_check is not None
    assert setup.storage_state is not None and setup.signed_in_as == "krama-bot"


def test_github_with_an_expired_session_is_not_used(tmp_path: Path) -> None:
    key = new_key()
    SessionVault(tmp_path, key).save("github", state(timedelta(hours=-1)))

    setup = target_setup("https://github.com", settings(tmp_path, key))

    assert setup.storage_state is None and setup.sign_in_problem is not None


def test_github_with_the_wrong_key_says_to_log_in_again(tmp_path: Path) -> None:
    SessionVault(tmp_path, new_key()).save("github", state())

    setup = target_setup("https://github.com", settings(tmp_path, new_key()))

    assert setup.storage_state is None and setup.sign_in_problem is not None
    assert "Log in again" in setup.sign_in_problem


def test_github_gives_the_browser_more_time_than_local_gitea(tmp_path: Path) -> None:
    key = new_key()
    SessionVault(tmp_path, key).save("github", state())
    github = target_setup("https://github.com", settings(tmp_path, key))

    config = github.browser_config(SessionConfig(base_url="https://github.com"))

    assert config.storage_state is not None
    assert config.action_timeout_ms == 10_000 and config.navigation_timeout_ms == 30_000
    other = target_setup("http://example.test", settings(tmp_path, key))
    assert other.browser_config(SessionConfig(base_url="x")) == SessionConfig(base_url="x")  # defaults kept
