"""Delete the benchmark repos in the GitHub test organization (#88). Dry run unless --apply.

Only repos owned by GITHUB_TEST_ORG whose name starts with the prefix (default `bench-`) are touched, so our own
or anyone else's repos can never be deleted by mistake. Setup and cleanup go through the REST API, never the UI
(docs/research/phase-3-together-github-account-and-benchmarks.md, rule 4).

Usage:
  uv run --no-project --python 3.12 scripts/github_cleanup.py                      # list what would go
  uv run --no-project --python 3.12 scripts/github_cleanup.py --apply              # delete them
  uv run --no-project --python 3.12 scripts/github_cleanup.py --older-than-hours 24 --apply

Reads GITHUB_BENCH_TOKEN and GITHUB_TEST_ORG from the environment or the repo-root .env. The token is never
printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"
DEFAULT_PREFIX = "bench-"


@dataclass(frozen=True)
class Repo:
    full_name: str
    owner: str
    name: str
    created_at: datetime


def load_env() -> dict[str, str]:
    """The repo-root .env, overridden by real environment variables."""
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"')
    return {**env, **{k: v for k, v in os.environ.items() if k.startswith("GITHUB_")}}


def to_delete(repos: list[Repo], org: str, prefix: str, older_than: timedelta, now: datetime) -> list[Repo]:
    """The repos to remove: owned by `org`, named `prefix...`, created at least `older_than` ago."""
    if not prefix:
        raise ValueError("an empty prefix would match every repo")
    return [
        r
        for r in repos
        if r.owner.lower() == org.lower() and r.name.startswith(prefix) and now - r.created_at >= older_than
    ]


class GitHub:
    def __init__(self, token: str) -> None:
        self._token = token

    def request(self, method: str, path: str) -> tuple[int, object]:
        req = urllib.request.Request(API + path, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return e.code, None

    def org_repos(self, org: str) -> list[Repo]:
        repos: list[Repo] = []
        for page in range(1, 51):  # 5,000 repos at most; the test org holds a handful
            status, body = self.request("GET", f"/orgs/{org}/repos?type=all&per_page=100&page={page}")
            if status != 200 or not isinstance(body, list):
                raise RuntimeError(f"listing {org}'s repos failed: HTTP {status} {_message(body)}")
            repos += [
                Repo(
                    full_name=r["full_name"],
                    owner=r["owner"]["login"],
                    name=r["name"],
                    created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                )
                for r in body
            ]
            if len(body) < 100:
                break
        return repos


def _message(body: object) -> str:
    return str(body.get("message", "")) if isinstance(body, dict) else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="really delete (default: dry run)")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help=f"repo name prefix (default {DEFAULT_PREFIX})")
    parser.add_argument("--older-than-hours", type=float, default=0.0, help="only repos at least this old")
    args = parser.parse_args(argv)

    env = load_env()
    token, org = env.get("GITHUB_BENCH_TOKEN"), env.get("GITHUB_TEST_ORG")
    if not token or not org:
        print("GITHUB_BENCH_TOKEN and GITHUB_TEST_ORG must be set (.env)", file=sys.stderr)
        return 2
    gh = GitHub(token)
    now = datetime.now(UTC)
    doomed = to_delete(gh.org_repos(org), org, args.prefix, timedelta(hours=args.older_than_hours), now)
    mode = "deleting" if args.apply else "dry run, would delete"
    print(f"{org}: {len(doomed)} repo(s) named {args.prefix}* ({mode})")
    failed = 0
    for repo in doomed:
        age_h = (now - repo.created_at).total_seconds() / 3600
        if not args.apply:
            print(f"  {repo.full_name}  ({age_h:.1f} h old)")
            continue
        status, body = gh.request("DELETE", f"/repos/{repo.full_name}")
        ok = status in (204, 404)  # 404: already gone
        failed += not ok
        print(f"  {repo.full_name}  -> {status}{'' if ok else ' ' + _message(body)}")
    if not args.apply and doomed:
        print("Run again with --apply to delete them.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
