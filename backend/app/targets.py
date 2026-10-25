"""What we know about a target site before planning or running on it: hints, and how to sign in.

The local Gitea is signed in as the demo user by a scripted login. GitHub uses the test account's stored,
encrypted browser session (#87): Krama never has its password.
"""

import asyncio
import base64
import json
import re
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from app.agent import SessionConfig
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


@dataclass(frozen=True)
class TargetSetup:
    site: str | None = None
    """Key into the planner's SITE_HINTS."""
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
    settle_ms: int = 0
    """How long to let a page's scripts load after navigating, before acting on it."""
    """A slow real site needs more than local Gitea's defaults (GitHub's editor took 4+ s to load, #89)."""

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
        )
    if _same_origin(target_url, settings.github_url):
        return _github_setup(settings)
    return TargetSetup()


def _github_setup(settings: Settings) -> TargetSetup:
    vault = SessionVault(settings.sessions_dir, settings.krama_storage_key.get_secret_value())
    try:
        state = vault.load(GITHUB.site)
    except SessionVaultError as e:
        return TargetSetup(site="github", sign_in_problem=f"{e}. Log in again.")
    problem = sign_in_problem(state, GITHUB)
    return TargetSetup(
        site="github",
        signed_in_as=settings.github_test_user or _cookie(state, "dotcom_user"),
        storage_state=None if problem else state,
        signed_in_check=GITHUB.signed_in_check,
        sign_in_problem=problem,
        action_timeout_ms=10_000,
        navigation_timeout_ms=30_000,
        settle_ms=2_500,
    )


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
