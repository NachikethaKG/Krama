"""What we know about a target site before planning or running on it: hints, and how to sign in.

Phase 1 knows one site, the local Gitea (signed in as the demo user). Phase 3 adds GitHub and stored
browser sessions (#87).
"""

import asyncio
import base64
import json
import re
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from app.agent.gitea_create_repo import login_steps
from app.agent.runlog import ScriptedStep
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


def target_setup(target_url: str, settings: Settings) -> TargetSetup:
    if _same_origin(target_url, settings.gitea_url):
        user = settings.gitea_demo_user
        return TargetSetup(
            site="gitea",
            preconditions=login_steps(user=user, password=settings.gitea_demo_password),
            signed_in_as=user,
            reset=lambda steps: _gitea_reset(steps, settings),
        )
    return TargetSetup()


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
