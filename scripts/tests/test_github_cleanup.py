"""scripts/github_cleanup.py picks only the test org's prefixed repos (#88).

Run: uv run --project backend pytest scripts/tests -o addopts=""
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from github_cleanup import Repo, to_delete

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def repo(full_name: str, hours_old: float = 2) -> Repo:
    owner, name = full_name.split("/")
    return Repo(full_name=full_name, owner=owner, name=name, created_at=NOW - timedelta(hours=hours_old))


REPOS = [
    repo("krama-bench/bench-new"),
    repo("krama-bench/bench-issues", hours_old=30),
    repo("krama-bench/docs"),  # no prefix
    repo("krama-bench/my-bench-notes"),  # prefix not at the start
    repo("someone-else/bench-new"),  # another owner
]


def test_only_the_orgs_prefixed_repos_are_picked() -> None:
    picked = to_delete(REPOS, "krama-bench", "bench-", timedelta(0), NOW)

    assert [r.full_name for r in picked] == ["krama-bench/bench-new", "krama-bench/bench-issues"]


def test_the_org_name_matches_case_insensitively() -> None:
    assert len(to_delete(REPOS, "Krama-Bench", "bench-", timedelta(0), NOW)) == 2


def test_age_limit_keeps_fresh_repos() -> None:
    picked = to_delete(REPOS, "krama-bench", "bench-", timedelta(hours=24), NOW)

    assert [r.full_name for r in picked] == ["krama-bench/bench-issues"]


def test_an_empty_prefix_is_refused() -> None:
    with pytest.raises(ValueError):
        to_delete(REPOS, "krama-bench", "", timedelta(0), NOW)
