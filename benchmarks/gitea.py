"""Gitea environment reset utility for benchmark runs.

Wipes target repositories via the Gitea REST API or admin CLI so each
benchmark trial starts in a pristine, reproducible state.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


class GiteaResetError(Exception):
    """Raised when Gitea environment reset fails."""


class GiteaTimeoutError(GiteaResetError):
    """Raised when Gitea environment reset times out."""


def _get_auth_header(user: str, password: str) -> str:
    creds = f"{user}:{password}".encode()
    return f"Basic {base64.b64encode(creds).decode()}"


def reset_gitea_api(
    base_url: str = "http://localhost:3001",
    user: str = "demo",
    password: str = "demo-local-only",
    repo_name: str | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """Wipe repositories for the specified user via Gitea REST API.

    Returns the list of deleted repository names.
    """
    clean_url = base_url.rstrip("/")
    auth = _get_auth_header(user, password)
    headers = {"Authorization": auth, "Accept": "application/json"}

    # 1. Check Gitea reachability
    version_req = urllib.request.Request(f"{clean_url}/api/v1/version", headers=headers)
    try:
        with urllib.request.urlopen(version_req, timeout=timeout) as resp:
            if resp.status != 200:
                raise GiteaResetError(f"Gitea healthcheck failed with HTTP status {resp.status}")
    except (TimeoutError, urllib.error.URLError) as e:
        if isinstance(e, TimeoutError) or "timed out" in str(e).lower():
            raise GiteaTimeoutError(f"Gitea healthcheck timed out connecting to {clean_url}: {e}") from e
        raise GiteaResetError(f"Cannot reach Gitea at {clean_url}: {e}") from e

    # 2. Determine repositories to delete
    repos_to_delete: list[str] = []
    if repo_name:
        repos_to_delete.append(repo_name)
    else:
        list_req = urllib.request.Request(f"{clean_url}/api/v1/users/{user}/repos", headers=headers)
        try:
            with urllib.request.urlopen(list_req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                repos_to_delete = [r["name"] for r in data if isinstance(r, dict) and "name" in r]
        except (TimeoutError, urllib.error.URLError) as e:
            if isinstance(e, TimeoutError) or "timed out" in str(e).lower():
                raise GiteaTimeoutError(f"Listing repos timed out for user {user}: {e}") from e
            raise GiteaResetError(f"Failed to list repositories for user {user}: {e}") from e

    # 3. Delete each repository
    deleted: list[str] = []
    for r_name in repos_to_delete:
        del_req = urllib.request.Request(
            f"{clean_url}/api/v1/repos/{user}/{r_name}",
            headers=headers,
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(del_req, timeout=timeout) as resp:
                if resp.status in (200, 204):
                    deleted.append(r_name)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Repo does not exist, state is already clean
                continue
            raise GiteaResetError(f"Failed to delete repo '{r_name}' (HTTP {e.code}): {e.reason}") from e
        except (TimeoutError, urllib.error.URLError) as e:
            if isinstance(e, TimeoutError) or "timed out" in str(e).lower():
                raise GiteaTimeoutError(f"Deleting repo '{r_name}' timed out: {e}") from e
            raise GiteaResetError(f"Network error deleting repo '{r_name}': {e}") from e

    return deleted


def reset_gitea_cli(repo_root: Path | None = None, timeout: float = 30.0) -> None:
    """Fallback reset invoking `docker compose exec gitea` or `just reset-gitea`."""
    root = repo_root or Path(__file__).resolve().parents[1]
    compose_file = root / "infra" / "docker-compose.yml"
    if not compose_file.exists():
        raise GiteaResetError(f"docker-compose.yml not found at {compose_file}")

    cmd = [
        "docker",
        "compose",
        "--env-file",
        ".env",
        "-f",
        str(compose_file),
        "exec",
        "-T",
        "-u",
        "git",
        "gitea",
        "gitea",
        "admin",
        "repo",
        "list",
    ]
    try:
        res = subprocess.run(
            cmd, cwd=root, capture_output=True, text=True, timeout=timeout, check=False
        )
        if res.returncode != 0:
            raise GiteaResetError(f"Gitea admin CLI failed: {res.stderr}")
    except subprocess.TimeoutExpired as e:
        raise GiteaTimeoutError(f"Gitea admin CLI timed out after {timeout}s: {e}") from e
    except Exception as e:
        raise GiteaResetError(f"Gitea CLI invocation error: {e}") from e


def reset_gitea(
    base_url: str | None = None,
    user: str | None = None,
    password: str | None = None,
    repo_name: str | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """Clean Gitea state before a trial run.

    Uses environment variables when defaults are not provided.
    """
    url = base_url or os.environ.get("GITEA_URL", "http://localhost:3001")
    demo_user = user or os.environ.get("GITEA_DEMO_USER", "demo")
    demo_pw = password or os.environ.get("GITEA_DEMO_PASSWORD", "demo-local-only")

    return reset_gitea_api(
        base_url=url,
        user=demo_user,
        password=demo_pw,
        repo_name=repo_name,
        timeout=timeout,
    )
