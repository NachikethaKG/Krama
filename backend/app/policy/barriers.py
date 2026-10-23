"""Bot-wall, CAPTCHA, and auth-wall detection for browser automation safety.

On a barrier the run stops (never solve, evade or bypass it, AGENTS.md §4). Two kinds of input:

1. Raw HTML (+ optional HTTP status), for callers that have it: script/iframe `src` URLs, widget classes
   (`g-recaptcha`, `h-captcha`, `cf-turnstile`, ...), `<input type=password>` and the 403/503 Cloudflare
   status-code path.
2. A `PageState` (url, title, aria_excerpt), which is all `Policy.check_action` receives. Detected from it:
   - Cloudflare interstitial titles ("Just a moment...", "Attention Required! | Cloudflare", ...);
   - "Verify you are human" as the page title or as the name of a checkbox / button / heading / iframe;
   - challenge widgets named in the ARIA tree: iframes or regions such as "Widget containing a Cloudflare
     security challenge", "reCAPTCHA", "hCaptcha ... security challenge", and the checkbox labels
     "I'm not a robot" / "I am human";
   - login walls: a password textbox on a login/auth path (/user/login, /login, /signin, /auth, /sso, ...)
     or on a page that is clearly a sign-in form (a "Sign in" / "Log in" button or heading). A password
     field on a settings page (e.g. Gitea's /user/settings/account) is never a login wall.

   NOT detectable through PageState, because it carries no HTML, headers or status code:
   - challenge scripts and widget containers without an accessible name (reCAPTCHA v3 / Enterprise and
     invisible Turnstile have no visible widget at all);
   - iframes whose title the ARIA snapshot doesn't expose, and anything outside the `main` landmark when the
     page has one (the observer's excerpt is `main` if present, else `body`);
   - HTTP 403/503 Cloudflare block pages, unless their title gives them away.
   Catching these on the `check_action` path would need PageState to carry more (e.g. the full-body ARIA,
   iframe sources or the response status). That is a port change, left to the port owner.

A bare mention of "recaptcha" or "hcaptcha" in page text (an issue titled "recaptcha", security docs) is
never a barrier on its own.
"""

import re
from typing import Any, Final
from urllib.parse import urlparse

from app.policy.barriers_github import evaluate_github_barriers
from app.policy.models import BarrierType, BarrierVerdict

__all__ = [
    "BarrierCheckResult",
    "BarrierType",
    "check_barrier",
]

BarrierCheckResult = BarrierVerdict


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
    "/sign_in",
    "/auth",
    "/sso",
    "/saml",
    "/users/sign_in",
    "/session/new",
    "/accounts/login",
    "/identity/login",
)

# Path prefixes of login/auth flows (Gitea: /user/login, /user/oauth2/<provider>).
_AUTH_PATH_PREFIXES: Final[tuple[str, ...]] = (
    "/user/login",
    "/user/oauth2/",
    "/login/",
    "/signin/",
    "/auth/",
    "/sso/",
    "/saml/",
)

# Settings pages have password fields ("Update Password") but are never a login wall.
_SETTINGS_PATH: Final[re.Pattern[str]] = re.compile(r"(?:^|/)settings(?:/|$)")

# --- Signals readable from the ARIA snapshot (Playwright `aria_snapshot` YAML) ---

_ARIA_PASSWORD_FIELD: Final[re.Pattern[str]] = re.compile(r'textbox\s+"[^"]*password[^"]*"', re.IGNORECASE)

_ARIA_SIGN_IN_FORM: Final[re.Pattern[str]] = re.compile(
    r'(?:button|heading)\s+"\s*(?:sign[\s-]?in|log[\s-]?in)\b[^"]*"', re.IGNORECASE
)
_HTML_SIGN_IN_FORM: Final[re.Pattern[str]] = re.compile(
    r"<(?:button|h[1-6])[^>]*>\s*(?:sign[\s-]?in|log[\s-]?in)\b"
    r"|<input[^>]+type=[\"']?submit[^>]+value=[\"']\s*(?:sign[\s-]?in|log[\s-]?in)",
    re.IGNORECASE,
)

_ARIA_WIDGET_ROLES = r"(?:iframe|document|region|group|figure|generic)"
_ARIA_CLOUDFLARE_WIDGET: Final[re.Pattern[str]] = re.compile(
    _ARIA_WIDGET_ROLES + r'\s+"[^"]*cloudflare security challenge[^"]*"', re.IGNORECASE
)
_ARIA_VERIFY_HUMAN: Final[re.Pattern[str]] = re.compile(
    r'(?:checkbox|button|heading|iframe)\s+"[^"]*verify you are human[^"]*"', re.IGNORECASE
)
_ARIA_RECAPTCHA_WIDGET: Final[re.Pattern[str]] = re.compile(
    r'(?:checkbox\s+"\s*i(?:\'|\u2019)?m not a robot\s*"|'
    + _ARIA_WIDGET_ROLES
    + r'\s+"[^"]*recaptcha[^"]*")',
    re.IGNORECASE,
)
_ARIA_HCAPTCHA_WIDGET: Final[re.Pattern[str]] = re.compile(
    r'(?:checkbox\s+"\s*i am human\s*"|' + _ARIA_WIDGET_ROLES + r'\s+"[^"]*hcaptcha[^"]*")',
    re.IGNORECASE,
)


def _detect_cloudflare(html: str, title: str, aria_excerpt: str, status_code: int | None) -> str | None:
    low_title = title.strip().lower()
    if any(cf_title in low_title for cf_title in _CLOUDFLARE_TITLES):
        return f"Cloudflare challenge page detected by title: '{title}'"

    if "verify you are human" in low_title:
        return f"Human-verification challenge page detected by title: '{title}'"

    if _ARIA_CLOUDFLARE_WIDGET.search(aria_excerpt):
        return "Cloudflare security challenge widget detected in the page ARIA snapshot"

    if _ARIA_VERIFY_HUMAN.search(aria_excerpt):
        return "'Verify you are human' challenge control detected in the page ARIA snapshot"

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

    if _ARIA_RECAPTCHA_WIDGET.search(aria_excerpt):
        return "Google reCAPTCHA widget present in ARIA snapshot"

    return None


def _detect_hcaptcha(html: str, aria_excerpt: str) -> str | None:
    if _HCAPTCHA_IFRAMES.search(html):
        return "hCaptcha challenge iframe detected"

    if _HCAPTCHA_SCRIPTS.search(html):
        return "hCaptcha script endpoint detected"

    if _HCAPTCHA_CLASSES.search(html):
        return "hCaptcha widget container detected"

    if _ARIA_HCAPTCHA_WIDGET.search(aria_excerpt):
        return "hCaptcha widget present in ARIA snapshot"

    return None


def _detect_auth_wall(html: str, url: str, aria_excerpt: str, allow_auth: bool) -> str | None:
    if allow_auth:
        return None

    path = urlparse(url).path.rstrip("/").lower()
    if _SETTINGS_PATH.search(path):
        return None  # e.g. "Update Password" on /user/settings/account: a security change, not a login wall

    low_combined = f"{html.lower()} {aria_excerpt.lower()}"
    has_password = bool(_PASSWORD_INPUT.search(html)) or bool(_ARIA_PASSWORD_FIELD.search(aria_excerpt))
    is_auth_path = any(path == seg or path.endswith(seg) for seg in _AUTH_PATH_SEGMENTS) or any(
        f"{path}/".startswith(prefix) for prefix in _AUTH_PATH_PREFIXES
    )
    is_sign_in_form = bool(_ARIA_SIGN_IN_FORM.search(aria_excerpt)) or bool(_HTML_SIGN_IN_FORM.search(html))

    if has_password and is_auth_path:
        return f"Unexpected authentication wall: login form at '{url}'"

    if has_password and is_sign_in_form:
        return "Unexpected authentication wall: sign-in form detected on page"

    if is_auth_path and ("sign in" in low_combined or "log in" in low_combined or "username" in low_combined):
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

    # 5. GitHub automation barriers
    if "github.com" in current_url.lower() or status_code in (429, 403) or "whoa there!" in html.lower():
        gh_verdict = evaluate_github_barriers(
            current_url,
            status_code=status_code or 200,
            headers=None,
            html_body=html,
            title=current_title,
        )
        if gh_verdict.should_stop and not (gh_verdict.barrier_type == BarrierType.AUTH_WALL and allow_auth):
            return gh_verdict

    return BarrierCheckResult(should_stop=False)
