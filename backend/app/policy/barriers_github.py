"""GitHub automation defense barrier detection (rate limits, abuse pages, Arkose, auth/sudo walls)."""

from __future__ import annotations

import re
from typing import Final

try:
    from app.policy.models import BarrierType, BarrierVerdict
except ImportError:  # pragma: no cover
    from backend.app.policy.models import (  # type: ignore[import-not-found,no-redef]
        BarrierType,
        BarrierVerdict,
    )

__all__ = [
    "ABUSE_PATTERNS",
    "CHALLENGE_PATTERNS",
    "SECONDARY_RATE_LIMIT_PATTERNS",
    "SUDO_PATTERNS",
    "evaluate_github_barriers",
]

SECONDARY_RATE_LIMIT_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"exceeded a secondary rate limit", re.IGNORECASE),
    re.compile(r"please wait a few minutes before you try again", re.IGNORECASE),
]

ABUSE_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"abuse detection mechanism", re.IGNORECASE),
    re.compile(r"<title>\s*Whoa there!\s*</title>", re.IGNORECASE),
    re.compile(r"<title>[^<]*Whoa there![^<]*</title>", re.IGNORECASE),
    re.compile(r"<h[1-6][^>]*>[^<]*Whoa there![^<]*</h[1-6]>", re.IGNORECASE),
]

CHALLENGE_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"arkoselabs\.com", re.IGNORECASE),
    re.compile(r"funcaptcha", re.IGNORECASE),
    re.compile(r"id=[\"'](?:captcha-and-sign-in|fc-iframe-wrap)[\"']", re.IGNORECASE),
    re.compile(r"id=[\"']inline-challenge-iframe[\"']", re.IGNORECASE),
    re.compile(r"class=[\"'][^\"']*(?:js-octocaptcha-frame|octocaptcha)[^\"']*[\"']", re.IGNORECASE),
]

SUDO_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"name=[\"']sudo_password[\"']", re.IGNORECASE),
    re.compile(r"action=[\"']/sudo[\"']", re.IGNORECASE),
    re.compile(r"action=[\"'][^\"']*/sessions/sudo[\"']", re.IGNORECASE),
]


def evaluate_github_barriers(
    url: str,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    html_body: str = "",
    *,
    title: str = "",
) -> BarrierVerdict:
    """Detect GitHub automation barriers (secondary rate limits, abuse pages, Arkose, auth/sudo).

    Returns a BarrierVerdict indicating whether automation should cleanly stop.
    Never attempts to solve, evade, or bypass the barrier (AGENTS.md §4).
    """
    headers_lower = {k.lower(): v for k, v in (headers or {}).items()}
    body = html_body or ""
    clean_url = (url or "").lower()
    page_title = title or ""

    # 1. Rate limits (HTTP 429/403, retry-after header, or secondary rate limit text)
    is_rate_limit = False
    if status_code in (429, 403):
        if (
            "retry-after" in headers_lower
            or any(p.search(body) for p in SECONDARY_RATE_LIMIT_PATTERNS)
            or status_code == 429
        ):
            is_rate_limit = True
    elif re.search(r"exceeded a secondary rate limit", body, re.IGNORECASE):
        is_rate_limit = True

    if is_rate_limit:
        retry = headers_lower.get("retry-after", "unspecified")
        return BarrierVerdict(
            should_stop=True,
            barrier_type=BarrierType.GITHUB_RATE_LIMIT,
            reason=f"GitHub secondary rate limit hit (retry-after: {retry}s)",
        )

    # 2. Abuse detection pages ("Whoa there!", "abuse detection mechanism")
    if (
        any(p.search(body) for p in ABUSE_PATTERNS)
        or "whoa there!" in page_title.lower()
        or "abuse detection mechanism" in page_title.lower()
    ):
        return BarrierVerdict(
            should_stop=True,
            barrier_type=BarrierType.GITHUB_ABUSE_PAGE,
            reason="GitHub abuse detection interstitial detected",
        )

    # 3. Interactive bot challenge (Arkose Labs / FunCAPTCHA / Octocaptcha)
    if any(p.search(body) for p in CHALLENGE_PATTERNS):
        return BarrierVerdict(
            should_stop=True,
            barrier_type=BarrierType.GITHUB_CHALLENGE,
            reason="GitHub interactive challenge (Arkose/FunCAPTCHA) detected",
        )

    # 4. Auth or Sudo wall (/login, /sessions/verified-device, sudo forms)
    if (
        "/login" in clean_url
        or "/sessions/verified-device" in clean_url
        or "/sessions/two-factor" in clean_url
        or any(p.search(body) for p in SUDO_PATTERNS)
    ):
        return BarrierVerdict(
            should_stop=True,
            barrier_type=BarrierType.AUTH_WALL,
            reason="GitHub session expired or sudo re-authentication barrier detected",
        )

    return BarrierVerdict(should_stop=False)
