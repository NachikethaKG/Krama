"""Automated unit tests for GitHub automation defense barrier detection."""

from pathlib import Path

import pytest

from app.policy.barriers import check_barrier
from app.policy.barriers_github import (
    ABUSE_PATTERNS,
    CHALLENGE_PATTERNS,
    SECONDARY_RATE_LIMIT_PATTERNS,
    SUDO_PATTERNS,
    evaluate_github_barriers,
)
from app.policy.models import BarrierType, BarrierVerdict

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "github_barriers"


def _read_fixture(filename: str) -> str:
    return (FIXTURES_DIR / filename).read_text(encoding="utf-8")


class TestGitHubBarrierDetectorHappyPath:
    """Happy path verification for each GitHub defense fixture."""

    def test_secondary_rate_limit_fixture(self) -> None:
        html = _read_fixture("secondary_rate_limit.html")
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=429,
            headers={"retry-after": "60"},
            html_body=html,
        )
        assert isinstance(verdict, BarrierVerdict)
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_RATE_LIMIT
        assert verdict.reason is not None
        assert "secondary rate limit" in verdict.reason.lower()
        assert "60s" in verdict.reason

    def test_abuse_detection_page_fixture(self) -> None:
        html = _read_fixture("abuse_detection_page.html")
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=200,
            headers={},
            html_body=html,
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_ABUSE_PAGE
        assert verdict.reason is not None
        assert "abuse detection" in verdict.reason.lower()

    def test_arkose_captcha_fixture(self) -> None:
        html = _read_fixture("arkose_captcha.html")
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo/issues/new",
            status_code=200,
            headers={},
            html_body=html,
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_CHALLENGE
        assert verdict.reason is not None
        assert "arkose" in verdict.reason.lower() or "funcaptcha" in verdict.reason.lower()

    def test_sudo_wall_fixture(self) -> None:
        html = _read_fixture("sudo_wall.html")
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo/settings/keys",
            status_code=200,
            headers={},
            html_body=html,
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.AUTH_WALL
        assert verdict.reason is not None
        assert "sudo" in verdict.reason.lower() or "session" in verdict.reason.lower()

    @pytest.mark.parametrize(
        "auth_url",
        [
            "https://github.com/login",
            "https://github.com/login?return_to=%2Fsettings",
            "https://github.com/sessions/verified-device",
            "https://github.com/sessions/two-factor",
        ],
    )
    def test_signin_and_device_verification_urls(self, auth_url: str) -> None:
        verdict = evaluate_github_barriers(url=auth_url, status_code=200, headers={}, html_body="")
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.AUTH_WALL
        assert verdict.reason is not None


class TestGitHubBarrierDetectorBaseline:
    """Negative and baseline checks asserting that normal pages do not stop execution."""

    def test_normal_repo_page_fixture(self) -> None:
        html = _read_fixture("normal_repo_page.html")
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            html_body=html,
        )
        assert verdict.should_stop is False
        assert verdict.barrier_type is None
        assert verdict.reason is None

    @pytest.mark.parametrize(
        "clean_url",
        [
            "https://github.com/krama-bench/test-repo",
            "https://github.com/krama-bench/test-repo/issues",
            "https://github.com/krama-bench/test-repo/pulls",
            "https://github.com/krama-bench/test-repo/blob/main/README.md",
        ],
    )
    def test_clean_github_navigation_urls(self, clean_url: str) -> None:
        verdict = evaluate_github_barriers(
            url=clean_url,
            status_code=200,
            headers={},
            html_body="<html><body><h1>Clean Content</h1></body></html>",
        )
        assert verdict.should_stop is False
        assert verdict.barrier_type is None


class TestGitHubBarrierDetectorEdgeCases:
    """Edge case resilience: status codes, header parsing, empty bodies, and malformed HTML."""

    def test_status_429_minimal_html_with_retry_after(self) -> None:
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=429,
            headers={"Retry-After": "60"},
            html_body="<p>Too Many Requests</p>",
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_RATE_LIMIT
        assert verdict.reason is not None
        assert "60s" in verdict.reason

    def test_status_429_missing_headers_and_empty_body(self) -> None:
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=429,
            headers=None,
            html_body="",
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_RATE_LIMIT
        assert verdict.reason is not None
        assert "unspecifieds" in verdict.reason

    def test_status_403_with_retry_after_header(self) -> None:
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=403,
            headers={"retry-after": "120"},
            html_body="",
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_RATE_LIMIT
        assert verdict.reason is not None
        assert "120s" in verdict.reason

    def test_status_403_with_secondary_rate_limit_text(self) -> None:
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=403,
            headers={},
            html_body="<span>You have exceeded a secondary rate limit.</span>",
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_RATE_LIMIT

    def test_status_403_without_rate_limit_markers(self) -> None:
        # Standard permission denied, not a rate limit
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=403,
            headers={},
            html_body="<h1>Forbidden: Access Denied</h1>",
        )
        assert verdict.should_stop is False

    def test_empty_body_and_null_headers(self) -> None:
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=200,
            headers=None,
            html_body="",
        )
        assert verdict.should_stop is False
        assert verdict.barrier_type is None
        assert verdict.reason is None

    def test_malformed_html_graceful_handling(self) -> None:
        malformed = "<<<<div>><<incomplete<form action='/sudo'>input name=sudo_password>>>"
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=200,
            headers=None,
            html_body=malformed,
        )
        # Sudo form marker inside malformed HTML still detects correctly without throwing
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.AUTH_WALL

    def test_case_insensitive_patterns(self) -> None:
        uppercase_abuse = "<html><title>WHOA THERE!</title><body>ABUSE DETECTION MECHANISM</body></html>"
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=200,
            headers={},
            html_body=uppercase_abuse,
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_ABUSE_PAGE

        uppercase_challenge = "<html><body><div ID='FC-IFRAME-WRAP'><iframe src='https://ARKOSELABS.COM'></iframe></div></body></html>"
        verdict = evaluate_github_barriers(
            url="https://github.com/krama-bench/test-repo",
            status_code=200,
            headers={},
            html_body=uppercase_challenge,
        )
        assert verdict.should_stop is True
        assert verdict.barrier_type == BarrierType.GITHUB_CHALLENGE

    def test_check_barrier_integration(self) -> None:
        """Verify that check_barrier() automatically triggers evaluate_github_barriers on GitHub URLs."""
        html = _read_fixture("arkose_captcha.html")
        result = check_barrier(
            html,
            url="https://github.com/krama-bench/test-repo",
            title="Verification · GitHub",
        )
        assert result.should_stop is True
        assert result.barrier_type == BarrierType.GITHUB_CHALLENGE


class TestPatternCoverage:
    """Direct pattern list validation."""

    def test_secondary_rate_limit_patterns(self) -> None:
        assert len(SECONDARY_RATE_LIMIT_PATTERNS) >= 2
        sample = "You have exceeded a secondary rate limit. Please wait a few minutes before you try again."
        assert all(p.search(sample) for p in SECONDARY_RATE_LIMIT_PATTERNS)

    def test_abuse_patterns(self) -> None:
        assert len(ABUSE_PATTERNS) >= 2
        assert any(p.search("abuse detection mechanism") for p in ABUSE_PATTERNS)
        assert any(p.search("<title>Whoa there!</title>") for p in ABUSE_PATTERNS)

    def test_challenge_patterns(self) -> None:
        assert any(p.search("https://client-api.arkoselabs.com") for p in CHALLENGE_PATTERNS)
        assert any(p.search("funcaptcha") for p in CHALLENGE_PATTERNS)
        assert any(p.search('id="fc-iframe-wrap"') for p in CHALLENGE_PATTERNS)

    def test_sudo_patterns(self) -> None:
        assert any(p.search('name="sudo_password"') for p in SUDO_PATTERNS)
        assert any(p.search('action="/sudo"') for p in SUDO_PATTERNS)
