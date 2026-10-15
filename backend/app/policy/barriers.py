"""Bot-wall, CAPTCHA, and auth-wall detection for browser automation safety."""

import re
from enum import StrEnum
from typing import Any, Final
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

__all__ = [
    "BarrierCheckResult",
    "BarrierType",
    "check_barrier",
]


class BarrierType(StrEnum):
    """Types of anti-bot or access restriction barriers."""

    CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
    RECAPTCHA = "recaptcha"
    HCAPTCHA = "hcaptcha"
    AUTH_WALL = "auth_wall"


class BarrierCheckResult(BaseModel):
    """Structured verdict from barrier detection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    should_stop: bool
    barrier_type: BarrierType | None = None
    reason: str | None = None


# --- Signatures and Patterns ---

_CLOUDFLARE_TITLES: Final[tuple[str, ...]] = (
    "just a moment...",
    "attention required! | cloudflare",
    "cloudflare | access denied",
)

_CLOUDFLARE_SCRIPTS: Final[re.Pattern[str]] = re.compile(
    r"""<script[^>]+src=["'][^"']*challenges\.cloudflare\.com""",
    re.IGNORECASE,
)

_CLOUDFLARE_IFRAMES: Final[re.Pattern[str]] = re.compile(
    r"""<iframe[^>]+src=["'][^"']*(?:challenges\.cloudflare\.com|turnstile)""",
    re.IGNORECASE,
)

_CLOUDFLARE_DOM_MARKERS: Final[re.Pattern[str]] = re.compile(
    r"""(?:id|class)=["'][^"']*(?:cf-wrapper|cf-turnstile|challenge-running|challenge-form|challenge-stage|cf-browser-verification)""",
    re.IGNORECASE,
)

_RECAPTCHA_SCRIPTS: Final[re.Pattern[str]] = re.compile(
    r"""<script[^>]+src=["'][^"']*(?:google\.com/recaptcha|recaptcha\.net/recaptcha|recaptcha/enterprise\.js|recaptcha/api\.js)""",
    re.IGNORECASE,
)

_RECAPTCHA_IFRAMES: Final[re.Pattern[str]] = re.compile(
    r"""<iframe[^>]+(?:src=["'][^"']*(?:google\.com/recaptcha|recaptcha\.net/recaptcha|recaptcha/api2)|title=["'][^"']*recaptcha)""",
    re.IGNORECASE,
)

_RECAPTCHA_CLASSES: Final[re.Pattern[str]] = re.compile(
    r"""(?:class|id)=["'][^"']*(?:g-recaptcha|g-recaptcha-response|grecaptcha-badge)""",
    re.IGNORECASE,
)

_HCAPTCHA_SCRIPTS: Final[re.Pattern[str]] = re.compile(
    r"""<script[^>]+src=["'][^"']*(?:hcaptcha\.com/1/api\.js|js\.hcaptcha\.com|assets\.hcaptcha\.com)""",
    re.IGNORECASE,
)

_HCAPTCHA_IFRAMES: Final[re.Pattern[str]] = re.compile(
    r"""<iframe[^>]+(?:src=["'][^"']*(?:hcaptcha\.com|assets\.hcaptcha\.com)|title=["'][^"']*hcaptcha)""",
    re.IGNORECASE,
)

_HCAPTCHA_CLASSES: Final[re.Pattern[str]] = re.compile(
    r"""(?:class|id)=["'][^"']*(?:h-captcha|h-captcha-response)""",
    re.IGNORECASE,
)

_PASSWORD_INPUT: Final[re.Pattern[str]] = re.compile(
    r"""<input[^>]+type=["']password["']|<input[^>]+type=password\b""",
    re.IGNORECASE,
)

_AUTH_PATH_SEGMENTS: Final[tuple[str, ...]] = (
    "/login",
    "/signin",
    "/sign-in",
    "/auth",
    "/users/sign_in",
    "/session/new",
    "/accounts/login",
    "/identity/login",
)


def _detect_cloudflare(html: str, title: str, aria_excerpt: str, status_code: int | None) -> str | None:
    low_title = title.strip().lower()
    if any(cf_title in low_title for cf_title in _CLOUDFLARE_TITLES):
        return f"Cloudflare challenge page detected by title: '{title}'"

    low_aria = aria_excerpt.lower()
    if "verify you are human" in low_aria or "cloudflare ray id" in low_aria:
        return "Cloudflare challenge detected in page ARIA accessibility tree"

    if status_code in (403, 503) and ("cloudflare" in html.lower() or _CLOUDFLARE_DOM_MARKERS.search(html)):
        return f"Cloudflare challenge response detected with HTTP {status_code}"

    if _CLOUDFLARE_IFRAMES.search(html):
        return "Cloudflare Turnstile challenge iframe detected"

    if _CLOUDFLARE_SCRIPTS.search(html):
        return "Cloudflare Turnstile script endpoint detected"

    if _CLOUDFLARE_DOM_MARKERS.search(html):
        return "Cloudflare challenge DOM container detected"

    return None


def _detect_recaptcha(html: str, aria_excerpt: str) -> str | None:
    if _RECAPTCHA_IFRAMES.search(html):
        return "Google reCAPTCHA iframe detected"

    if _RECAPTCHA_SCRIPTS.search(html):
        return "Google reCAPTCHA script detected"

    if _RECAPTCHA_CLASSES.search(html):
        return "Google reCAPTCHA widget container detected"

    if "recaptcha" in aria_excerpt.lower():
        return "Google reCAPTCHA element present in ARIA snapshot"

    return None


def _detect_hcaptcha(html: str, aria_excerpt: str) -> str | None:
    if _HCAPTCHA_IFRAMES.search(html):
        return "hCaptcha challenge iframe detected"

    if _HCAPTCHA_SCRIPTS.search(html):
        return "hCaptcha script endpoint detected"

    if _HCAPTCHA_CLASSES.search(html):
        return "hCaptcha widget container detected"

    if "hcaptcha" in aria_excerpt.lower():
        return "hCaptcha element present in ARIA snapshot"

    return None


def _detect_auth_wall(html: str, url: str, aria_excerpt: str, allow_auth: bool) -> str | None:
    if allow_auth:
        return None

    low_aria = aria_excerpt.lower()
    low_html = html.lower()

    has_password = bool(_PASSWORD_INPUT.search(html)) or 'textbox "password"' in low_aria

    parsed = urlparse(url)
    path = parsed.path.rstrip("/").lower()
    is_auth_path = any(path == seg or path.endswith(seg) for seg in _AUTH_PATH_SEGMENTS)

    combined_text = f"{low_html} {low_aria}"

    if has_password and is_auth_path:
        return f"Unexpected authentication wall: login form at '{url}'"

    if has_password:
        return "Unexpected authentication wall: password input detected on page"

    if is_auth_path and (
        "sign in" in combined_text or "log in" in combined_text or "username" in combined_text
    ):
        return f"Unexpected authentication wall: redirected to login path '{url}'"

    return None


def check_barrier(
    page_or_html: Any,
    *,
    url: str | None = None,
    title: str | None = None,
    status_code: int | None = None,
    aria_excerpt: str | None = None,
    allow_auth: bool = False,
) -> BarrierCheckResult:
    """Analyze page contents and metadata for bot barriers, CAPTCHAs, or login walls.

    Never attempts to solve, evade, or bypass the barrier; returns an explicit stop signal immediately.
    """
    html = ""
    current_url = url or ""
    current_title = title or ""
    excerpt = aria_excerpt or ""

    if isinstance(page_or_html, str):
        html = page_or_html
    elif hasattr(page_or_html, "url") and hasattr(page_or_html, "title"):
        current_url = current_url or str(getattr(page_or_html, "url", "") or "")
        current_title = current_title or str(getattr(page_or_html, "title", "") or "")
        excerpt = excerpt or str(getattr(page_or_html, "aria_excerpt", "") or "")
        if hasattr(page_or_html, "html"):
            html = str(getattr(page_or_html, "html", "") or "")
    elif isinstance(page_or_html, dict):
        html = str(page_or_html.get("html", "") or "")
        current_url = current_url or str(page_or_html.get("url", "") or "")
        current_title = current_title or str(page_or_html.get("title", "") or "")
        excerpt = excerpt or str(page_or_html.get("aria_excerpt", "") or "")

    # 1. Cloudflare Challenge / Turnstile
    cf_reason = _detect_cloudflare(html, current_title, excerpt, status_code)
    if cf_reason:
        return BarrierCheckResult(
            should_stop=True,
            barrier_type=BarrierType.CLOUDFLARE_CHALLENGE,
            reason=cf_reason,
        )

    # 2. Google reCAPTCHA
    recaptcha_reason = _detect_recaptcha(html, excerpt)
    if recaptcha_reason:
        return BarrierCheckResult(
            should_stop=True,
            barrier_type=BarrierType.RECAPTCHA,
            reason=recaptcha_reason,
        )

    # 3. hCaptcha
    hcaptcha_reason = _detect_hcaptcha(html, excerpt)
    if hcaptcha_reason:
        return BarrierCheckResult(
            should_stop=True,
            barrier_type=BarrierType.HCAPTCHA,
            reason=hcaptcha_reason,
        )

    # 4. Auth-walls / Login barriers
    auth_reason = _detect_auth_wall(html, current_url, excerpt, allow_auth)
    if auth_reason:
        return BarrierCheckResult(
            should_stop=True,
            barrier_type=BarrierType.AUTH_WALL,
            reason=auth_reason,
        )

    return BarrierCheckResult(should_stop=False)
