"""What we know about a target site before planning or running on it: hints, and how to sign in.

The local Gitea is signed in as the demo user by a scripted login. GitHub uses the test account's stored,
encrypted browser session (#87): Krama never has its password.
"""

import asyncio
import base64
import html
import json
import re
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from playwright.async_api import Page

from app.agent import SessionConfig, start_path
from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import ScriptedStep
from app.agent.stored_session import (
    GITHUB,
    SessionVault,
    SessionVaultError,
    SignedInCheck,
    StorageState,
    cookie_expiry,
    sign_in_problem,
)
from app.config import Settings

type StoredStep = Mapping[str, Any]
"""A stored workflow step as in workflow_steps: action, target, before_state, ..."""
type Reset = Callable[[Sequence[StoredStep]], Awaitable[list[str]]]


class ResetError(RuntimeError):
    """The target couldn't be brought back to a workflow's starting state."""


class PrepareError(RuntimeError):
    """The target couldn't be made ready for planning (e.g. the practice repository is missing)."""


@dataclass(frozen=True)
class TargetSetup:
    site: str | None = None
    """Key into the planner's SITE_HINTS."""
    login_path: str | None = None
    """Where a human signs in by hand (a sign-in run, ADR 0007). None: the site has no sign-in to offer."""
    account_of: Callable[[Page, StorageState], Awaitable[str | None]] | None = None
    """The account the browser is signed in as, or None if it isn't (checked after a sign-in run)."""
    session_cookie: str | None = None
    """The sign-in cookie whose expiry is the stored session's (ADR 0007)."""
    sign_in_hosts: tuple[str, ...] = ()
    """Other hosts (`host[:port]`) a human may open while signing in during a takeover (ADR 0008), besides the
    target's own. Everything else is blocked."""
    preconditions: list[ScriptedStep] = field(default_factory=list)
    """Run before planning and before step 1 (e.g. signing in). Never part of the plan or the recording."""
    signed_in_as: str | None = None
    reset: Reset | None = None
    """Before a reverify (#77): undo what a stored workflow creates, so its replay starts where it once did.
    Returns what it did; raises ResetError. None: the target has no reset."""
    storage_state: StorageState | None = None
    """A stored signed-in browser session to open the browser with (#87). A secret: never log or store it."""
    signed_in_check: SignedInCheck | None = None
    """Run on the first page: False means the stored session no longer signs us in."""
    sign_in_problem: str | None = None
    """Why the target can't be used signed in (no session, expired, unreadable): stop before opening it."""
    action_timeout_ms: int | None = None
    navigation_timeout_ms: int | None = None
    practice_repo: str | None = None
    """owner/name of a repository on the test account for tasks that need an existing one and name none
    (#325): learners see how it's done, not on their own data. None: the target has none."""
    prepare: Callable[[], Awaitable[None]] | None = None
    """Run before planning (e.g. create the practice repository if it's missing). Raises PrepareError."""
    settle_ms: int = 0
    """How long to let a page's scripts load after navigating, before acting on it."""
    """A slow real site needs more than local Gitea's defaults (GitHub's editor took 4+ s to load, #89)."""
    verify_timeout_s: float | None = None
    """How long to keep re-checking a step's expected state (None: the run's default). GitHub's dialogs take
    3+ s to close and list what they created (#89)."""
    anonymous_ok: bool = False
    """Any other site (ADR 0012): a run uses the user's stored session if there is one, else runs signed out
    (public pages). False (Gitea, GitHub): "Do it for me" needs the user's own session (ADR 0007)."""

    def browser_config(self, config: SessionConfig) -> SessionConfig:
        """`config` with this target's signed-in session and timeouts (the run's and planner's browser)."""
        changes: dict[str, Any] = {}
        if self.storage_state is not None:
            changes["storage_state"] = self.storage_state
        if self.action_timeout_ms is not None:
            changes["action_timeout_ms"] = self.action_timeout_ms
        if self.navigation_timeout_ms is not None:
            changes["navigation_timeout_ms"] = self.navigation_timeout_ms
        return replace(config, **changes)


def target_setup(target_url: str, settings: Settings) -> TargetSetup:
    if _same_origin(target_url, settings.gitea_url):
        user = settings.gitea_demo_user
        return TargetSetup(
            site="gitea",
            preconditions=login_steps(user=user, password=settings.gitea_demo_password),
            signed_in_as=user,
            reset=lambda steps: _gitea_reset(steps, settings),
            login_path="/user/login",
            account_of=_gitea_account,
            session_cookie="i_like_gitea",
        )
    if _same_origin(target_url, settings.github_url):
        return _github_setup(settings)
    if not target_url.lower().startswith(("http://", "https://")):
        return TargetSetup()
    # Any other site (ADR 0012): keyed by its origin; a sign-in starts on the page the user named.
    return TargetSetup(site=origin_of(target_url), login_path=start_path(target_url), anonymous_ok=True)


def origin_of(url: str) -> str:
    """`scheme://host[:port]`, lower case: the key of a site's stored session (ADR 0012)."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def site_key(url: str, settings: Settings) -> str:
    """The stored-session key for `url`: gitea or github for those two (ADR 0007), else the origin."""
    if _same_origin(url, settings.gitea_url) or _same_origin(origin_of(url), settings.gitea_url):
        return "gitea"
    if _same_origin(url, settings.github_url) or _same_origin(origin_of(url), settings.github_url):
        return "github"
    return origin_of(url)


def _github_setup(settings: Settings) -> TargetSetup:
    vault = SessionVault(settings.sessions_dir, settings.krama_storage_key.get_secret_value())
    try:
        state = vault.load(GITHUB.site)
    except SessionVaultError as e:
        return TargetSetup(site="github", sign_in_problem=f"{e}. Log in again.")
    problem = sign_in_problem(state, GITHUB)
    practice = (
        f"{settings.github_test_org}/{settings.github_practice_repo}"
        if settings.github_test_org and settings.github_bench_token.get_secret_value()
        else None
    )

    async def prepare() -> None:
        assert practice is not None
        await asyncio.to_thread(_ensure_github_repo, settings, practice)

    return TargetSetup(
        site="github",
        signed_in_as=settings.github_test_user or _cookie(state, "dotcom_user"),
        storage_state=None if problem else state,
        signed_in_check=GITHUB.signed_in_check,
        sign_in_problem=problem,
        login_path="/login",
        account_of=_github_account,
        session_cookie=GITHUB.session_cookie,
        practice_repo=practice,
        prepare=prepare if practice else None,
        action_timeout_ms=10_000,
        navigation_timeout_ms=30_000,
        settle_ms=2_500,
        verify_timeout_s=15.0,
    )


_GITEA_USERNAME = re.compile(r'<input[^>]*\sname="name"[^>]*\svalue="([^"]+)"')


async def _gitea_account(page: Page, state: StorageState) -> str | None:
    """Who the Gitea session belongs to: the account settings page, which opens only when signed in and holds
    the username. (Gitea's API wants a token and answers 401 to a browser session, so asking it always said
    "not signed in" (#431 gate).)"""
    response = await page.request.get(urljoin(page.url, "/user/settings"), max_redirects=0)
    if response.status != 200:
        return None  # signed out: Gitea redirects to /user/login
    found = _GITEA_USERNAME.search(await response.text())
    return html.unescape(found.group(1)) if found else None


async def _github_account(page: Page, state: StorageState) -> str | None:
    """GitHub names the signed-in account in a cookie, and only when signed in."""
    if not await GITHUB.signed_in_check(page):
        return None
    return _cookie(state, "dotcom_user")


def _cookie(state: StorageState | None, name: str) -> str | None:
    return next((c.get("value") for c in (state or {}).get("cookies", []) if c.get("name") == name), None)


def session_expires(state: StorageState | None) -> str | None:
    """When the GitHub session cookie expires, for messages (never the cookie itself)."""
    expires = cookie_expiry(state or {}, GITHUB.session_cookie)
    return f"{expires:%Y-%m-%d %H:%M} UTC" if expires else None


# A stored step that creates something, and the Gitea API path that deletes it again. Field names match by
# their start, ignoring case ("Repository Name *"). Workflows that can run twice (an issue, a setting) need
# no reset.
_CREATES = re.compile(r"^(?P<what>repository name|branch name|name your file)\b", re.IGNORECASE)
_REPO_PAGE = re.compile(r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+)/")
_NEW_FILE_PAGE = re.compile(r"^/[^/]+/[^/]+/_new/(?P<branch>[^/]+)/")


async def _gitea_reset(steps: Sequence[StoredStep], settings: Settings) -> list[str]:
    """Delete the repository, branch or file a stored Gitea workflow creates (missing already is fine)."""
    paths: list[str] = []
    files: list[tuple[str, str]] = []  # (contents API path, branch)
    for step in steps:
        action, target = step.get("action") or {}, step.get("target") or {}
        match = _CREATES.match(str(target.get("name") or ""))
        value = str(action.get("value") or "")
        if action.get("type") != "fill" or match is None or not value:
            continue
        if match["what"].lower() == "repository name":
            paths.append(f"/api/v1/repos/{quote(settings.gitea_demo_user)}/{quote(value)}")
            continue
        url = str((step.get("before_state") or {}).get("url") or "")
        page = _REPO_PAGE.match(url)
        if page is None:
            raise ResetError(f"step {step.get('seq')} creates something, but its repository is unknown")
        repo = f"/api/v1/repos/{quote(page['owner'])}/{quote(page['repo'])}"
        if match["what"].lower() == "branch name":
            paths.append(f"{repo}/branches/{quote(value)}")
            continue
        new_file = _NEW_FILE_PAGE.match(url)
        files.append((f"{repo}/contents/{quote(value)}", new_file["branch"] if new_file else ""))
    done = []
    for path, branch in files:
        status = await asyncio.to_thread(_gitea_delete_file, settings, path, branch)
        if status not in (200, 204, 404):
            raise ResetError(f"DELETE {path} returned {status}")
        done.append(f"DELETE {path} -> {status}")
    for path in paths:
        status = await asyncio.to_thread(_gitea_delete, settings, path)
        if status not in (204, 404):
            raise ResetError(f"DELETE {path} returned {status}")
        done.append(f"DELETE {path} -> {status}")
    return done


def _gitea_delete(settings: Settings, path: str) -> int:
    return _gitea_call(settings, "DELETE", path)[0]


def _gitea_delete_file(settings: Settings, path: str, branch: str) -> int:
    """Gitea deletes a file by its current sha, so look it up first."""
    query = f"?ref={quote(branch)}" if branch else ""
    status, body = _gitea_call(settings, "GET", path + query)
    if status != 200:
        return status
    sha = json.loads(body).get("sha")
    payload = {
        "sha": sha,
        "message": "Reset for re-verification (Krama)",
        **({"branch": branch} if branch else {}),
    }
    return _gitea_call(settings, "DELETE", path, payload)[0]


def _gitea_call(
    settings: Settings, method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, str]:
    auth = base64.b64encode(f"{settings.gitea_demo_user}:{settings.gitea_demo_password}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(_ipv4(settings.gitea_url.rstrip("/") + path), data=data, method=method)
    request.add_header("Authorization", f"Basic {auth}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return int(response.status), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError) as e:
        raise ResetError(f"Gitea isn't reachable: {e}") from e


def _ipv4(url: str) -> str:
    """localhost -> 127.0.0.1: on Windows, Python tries IPv6 first and every request waits ~21 s."""
    parts = urlsplit(url)
    if parts.hostname != "localhost":
        return url
    return urlunsplit(parts._replace(netloc="127.0.0.1" + (f":{parts.port}" if parts.port else "")))


def _same_origin(a: str, b: str) -> bool:
    def norm(url: str) -> str:
        return url.rstrip("/").lower().replace("://127.0.0.1", "://localhost")

    return norm(a) == norm(b)


def _ensure_github_repo(settings: Settings, full_name: str) -> None:
    """Create the practice repository (private, with a README so it has a main branch) unless it exists."""
    status, _ = _github_call(settings, "GET", f"/repos/{full_name}")
    if status == 200:
        return
    if status != 404:
        raise PrepareError(f"GET /repos/{full_name} returned {status}")
    org, name = full_name.split("/", 1)
    body = {
        "name": name,
        "private": True,
        "auto_init": True,
        "description": "Krama practice repository: tutorials run here. Safe to delete; it is recreated.",
    }
    status, _ = _github_call(settings, "POST", f"/orgs/{org}/repos", body)
    if status not in (201, 422):  # 422: created meanwhile by another task
        raise PrepareError(f"POST /orgs/{org}/repos returned {status}")


def _github_call(
    settings: Settings, method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(settings.github_api_url.rstrip("/") + path, data=data, method=method)
    request.add_header("Authorization", f"Bearer {settings.github_bench_token.get_secret_value()}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "krama")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return int(response.status), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError) as e:
        raise PrepareError(f"{method} {path} failed: {e}") from e
