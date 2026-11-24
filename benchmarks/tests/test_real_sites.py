"""The real-site benchmark (#481): its task file and its pass rule. No network, no API."""

from collections import Counter

import pytest

from benchmarks.real_sites import SiteResult, load_tasks, markdown, matches, summary


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
