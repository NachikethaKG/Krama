"""The real-site benchmark (#481): its task file and its pass rule. No network, no API."""

from collections import Counter
from pathlib import Path

import pytest

from benchmarks.real_sites import (
    SiteResult,
    SiteTask,
    load_saved,
    load_tasks,
    markdown,
    matches,
    quota_allows,
    still_to_run,
    summary,
    write_results,
)


def test_the_gate_file_has_12_sites_with_2_tasks_each() -> None:
    tasks = load_tasks()

    assert len(tasks) == 24
    assert len({t.name for t in tasks}) == 24
    assert set(Counter(t.site for t in tasks).values()) == {2}
    own = {t.site for t in tasks if t.account == "own"}
    # Chosen by Vishwas, 2026-11-24; Habitica replaced Todoist (an invisible CAPTCHA blocks Krama's browser).
    assert own == {"Trello", "Habitica", "Codeberg", "GitLab.com"}
    assert {t.account for t in tasks} == {"none", "own"}


def test_no_gate_site_was_used_while_building_phase_7() -> None:
    spike = (
        "wikipedia.org",
        "openstreetmap.org",
        "demo.playwright.dev",
        "docs.python.org",
        "developer.mozilla.org",
    )
    assert [t.target for t in load_tasks() if any(s in t.target for s in spike)] == []


@pytest.mark.parametrize(
    ("success", "url", "title", "ok"),
    [
        ({"url_matches": "^/ebooks/\\d+"}, "/ebooks/1342", "Pride", True),
        ({"url_matches": "^/ebooks/\\d+"}, "/ebooks/search/?query=pride", None, False),
        ({"url_matches": "^/package/express.*versions"}, "/package/express?activeTab=versions", None, True),
        ({"title_contains": "flask"}, "/project/flask/", "Flask · PyPI", True),
        ({}, None, None, True),
        ({"url_matches": "x"}, None, None, False),
    ],
)
def test_success_matching(success: dict[str, str], url: str | None, title: str | None, ok: bool) -> None:
    assert matches(success, url, title) is ok


def test_a_task_passes_only_verified_with_a_clean_replay() -> None:
    good = SiteResult("a", "A", outcome="verified", takeovers=1, replay="verified", replay_llm_calls=0)
    assert good.passed
    assert not SiteResult(
        "b", "B", outcome="verified", takeovers=2, replay="verified", replay_llm_calls=0
    ).passed
    assert not SiteResult("c", "C", outcome="verified", replay="verified", replay_llm_calls=1).passed
    assert not SiteResult("d", "D", outcome="verified", replay="failed", replay_llm_calls=0).passed
    assert not SiteResult("e", "E", outcome="wrong_page", replay=None).passed

    results = [
        good,
        SiteResult("f", "F", outcome="needs_sign_in"),
        SiteResult("g", "G", outcome="paused", llm_calls=7),
    ]
    s = summary(results)
    assert (s["tasks"], s["ran"], s["passed"], s["needs_sign_in"]) == (3, 2, 1, ["f"])
    assert "**1/3 passed**" in markdown(results)


def test_a_task_the_quota_stopped_is_no_verdict() -> None:
    # #494: on Gemini's free tier (20 requests per model per day) a task can run out halfway.
    results = [SiteResult("a", "A", outcome="quota"), SiteResult("b", "B", outcome="failed")]

    s = summary(results)

    assert (s["ran"], s["still_to_run"]) == (1, ["a"])


def test_a_resumed_gate_runs_only_the_tasks_without_a_verdict(tmp_path: Path) -> None:
    tasks = [SiteTask(n, n.upper(), "https://example.org", "Do it") for n in ("a", "b", "c", "d", "e")]
    done = [
        SiteResult("a", "A", outcome="verified", replay="verified", replay_llm_calls=0),
        SiteResult("b", "B", outcome="failed", why="no such button"),
        SiteResult("c", "C", outcome="quota"),
        SiteResult("d", "D", outcome="needs_sign_in"),
    ]
    write_results(tmp_path, tmp_path / "gate.json", done)

    saved = load_saved(tmp_path / "gate.json")

    assert saved["b"].why == "no such button"
    assert [t.name for t in still_to_run(tasks, saved)] == ["c", "d", "e"]
    assert "**1/4 passed**" in (tmp_path / "gate.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(("used", "ok"), [(0, True), (25, True), (26, False), (40, False)])
def test_no_task_starts_without_room_for_it_today(used: int, ok: bool) -> None:
    assert quota_allows(used, daily=40, per_task=15) is ok
