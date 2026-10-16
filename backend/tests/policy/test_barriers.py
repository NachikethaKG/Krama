"""Tests for bot-wall, CAPTCHA, and auth-wall detection."""

from pathlib import Path

import pytest

from app.contracts_gen.common_schema import Action, Target
from app.policy.barriers import BarrierCheckResult, BarrierType, check_barrier
from app.policy.service import PolicyService
from app.ports.models import PageState, StepRef

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    return path.read_text(encoding="utf-8")


def test_detect_recaptcha_v2_offline_fixture() -> None:
    html = read_fixture("recaptcha_v2.html")
    result: BarrierCheckResult = check_barrier(html)
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.RECAPTCHA
    assert result.reason is not None
    assert "recaptcha" in result.reason.lower()


def test_detect_recaptcha_v3_enterprise_offline_fixture() -> None:
    html = read_fixture("recaptcha_v3_enterprise.html")
    result: BarrierCheckResult = check_barrier(html)
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.RECAPTCHA
    assert result.reason is not None
    assert "recaptcha" in result.reason.lower()


def test_detect_hcaptcha_offline_fixture() -> None:
    html = read_fixture("hcaptcha.html")
    result: BarrierCheckResult = check_barrier(html)
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.HCAPTCHA
    assert result.reason is not None
    assert "hcaptcha" in result.reason.lower()


def test_detect_cloudflare_turnstile_offline_fixture() -> None:
    html = read_fixture("cloudflare_turnstile.html")
    result: BarrierCheckResult = check_barrier(html)
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.CLOUDFLARE_CHALLENGE
    assert result.reason is not None
    assert "cloudflare" in result.reason.lower() or "turnstile" in result.reason.lower()


def test_detect_cloudflare_challenge_interstitial_offline_fixture() -> None:
    html = read_fixture("cloudflare_challenge.html")
    result: BarrierCheckResult = check_barrier(html, title="Just a moment...")
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.CLOUDFLARE_CHALLENGE
    assert result.reason is not None
    assert "just a moment" in result.reason.lower()


def test_detect_auth_wall_offline_fixture() -> None:
    html = read_fixture("auth_wall.html")
    result: BarrierCheckResult = check_barrier(html, url="/login")
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.AUTH_WALL
    assert result.reason is not None
    assert "authentication wall" in result.reason.lower()


def test_negative_control_clean_dashboard() -> None:
    html = read_fixture("clean_dashboard.html")
    result: BarrierCheckResult = check_barrier(html, url="/dashboard", title="Dashboard - Krama")
    assert result.should_stop is False
    assert result.barrier_type is None
    assert result.reason is None


def test_negative_control_clean_docs_with_security_mentions() -> None:
    html = read_fixture("clean_docs.html")
    result: BarrierCheckResult = check_barrier(html, url="/docs/security", title="Security Docs")
    assert result.should_stop is False
    assert result.barrier_type is None
    assert result.reason is None


@pytest.mark.parametrize(
    "cf_title",
    [
        "Just a moment...",
        "Attention Required! | Cloudflare",
        "Cloudflare | Access denied",
    ],
)
def test_detect_cloudflare_by_title_alone(cf_title: str) -> None:
    result = check_barrier("<html><body>Loading...</body></html>", title=cf_title)
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.CLOUDFLARE_CHALLENGE


@pytest.mark.parametrize("status_code", [403, 503])
def test_detect_cloudflare_http_status_codes(status_code: int) -> None:
    html = "<html><body>Error from Cloudflare challenge service</body></html>"
    result = check_barrier(html, status_code=status_code)
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.CLOUDFLARE_CHALLENGE


def test_auth_wall_respects_allow_auth_parameter() -> None:
    html = read_fixture("auth_wall.html")
    # When allow_auth is True (e.g. planned sign-in step), should not stop
    allowed_result = check_barrier(html, url="/login", allow_auth=True)
    assert allowed_result.should_stop is False

    # When allow_auth is False (unexpected login wall during run), must stop
    blocked_result = check_barrier(html, url="/login", allow_auth=False)
    assert blocked_result.should_stop is True
    assert blocked_result.barrier_type == BarrierType.AUTH_WALL


@pytest.mark.anyio
async def test_policy_service_stops_on_captcha() -> None:
    service = PolicyService()
    step = StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(name="Submit", role="button"),
        instruction_text="Submit form",
    )
    captcha_page = PageState(
        url="/submit",
        title="Just a moment...",
        aria_excerpt='heading "Just a moment..." button "Verify you are human"',
    )

    decision = await service.check_action(step, captcha_page)
    assert decision.verdict == "stop"
    assert decision.reason == "captcha"
    assert "just a moment" in decision.message.lower()


@pytest.mark.anyio
async def test_policy_service_stops_on_auth_wall() -> None:
    service = PolicyService()
    step = StepRef(
        seq=2,
        action=Action(type="click"),
        target=Target(name="Edit", role="link"),
        instruction_text="Edit file",
    )
    auth_page = PageState(
        url="/login",
        title="Sign In",
        aria_excerpt='form "Sign In" textbox "Username" textbox "Password"',
    )

    # Injecting HTML simulation via aria excerpt and URL
    decision = await service.check_action(step, auth_page)
    assert decision.verdict == "stop"
    assert decision.reason == "auth_wall"


# --- Review regressions (#61, #62) ---

GITEA_ACCOUNT_SETTINGS_ARIA = "\n".join(
    [
        '- heading "Password" [level=4]',
        '- textbox "Current Password"',
        '- textbox "New Password"',
        '- textbox "Confirm Password"',
        '- button "Update Password"',
    ]
)


def _register_step() -> StepRef:
    return StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(name="Register", role="button"),
        instruction_text="Register",
    )


@pytest.mark.anyio
async def test_update_password_on_settings_pauses_instead_of_auth_wall_stop() -> None:
    """Regression: any password textbox was treated as a login wall and stopped the run."""
    step = StepRef(
        seq=4,
        action=Action(type="click"),
        target=Target(name="Update Password", role="button"),
        instruction_text="Click Update Password",
    )
    page = PageState(url="/user/settings/account", title="Account", aria_excerpt=GITEA_ACCOUNT_SETTINGS_ARIA)

    decision = await PolicyService().check_action(step, page)

    assert decision.verdict == "pause"
    assert decision.reason == "destructive_action"


def test_password_field_on_settings_page_is_not_auth_wall() -> None:
    page = PageState(url="/user/settings/account", title="Account", aria_excerpt=GITEA_ACCOUNT_SETTINGS_ARIA)
    assert check_barrier(page).should_stop is False


@pytest.mark.parametrize(
    "url", ["/user/login", "/login", "/signin", "/user/oauth2/github", "/auth", "/sso/start"]
)
def test_password_field_on_login_path_is_auth_wall(url: str) -> None:
    aria = '- textbox "Username or Email Address"\n- textbox "Password"'
    result = check_barrier(PageState(url=url, title="Sign In", aria_excerpt=aria))
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.AUTH_WALL


def test_sign_in_form_on_other_path_is_auth_wall() -> None:
    aria = '- heading "Sign In" [level=4]\n- textbox "Password"\n- button "Sign In"'
    result = check_barrier(PageState(url="/demo/private-repo", title="Gitea", aria_excerpt=aria))
    assert result.should_stop is True
    assert result.barrier_type == BarrierType.AUTH_WALL


def test_password_field_without_sign_in_form_off_login_path_is_not_auth_wall() -> None:
    aria = '- textbox "Webhook Secret Password"\n- button "Add Webhook"'
    result = check_barrier(PageState(url="/demo/repo/webhooks/new", title="Webhooks", aria_excerpt=aria))
    assert result.should_stop is False


@pytest.mark.parametrize(
    ("title", "aria"),
    [
        ("Issue #3: recaptcha is broken", '- heading "recaptcha is broken"\n- paragraph: hcaptcha too'),
        ("Security docs", "- paragraph: We use reCAPTCHA, hCaptcha and Cloudflare Turnstile against bots."),
    ],
)
def test_bare_captcha_mention_in_page_text_does_not_stop(title: str, aria: str) -> None:
    """Regression: an issue titled "recaptcha" stopped the run."""
    result = check_barrier(PageState(url="/demo/repo/issues/3", title=title, aria_excerpt=aria))
    assert result.should_stop is False


@pytest.mark.parametrize(
    ("title", "aria", "barrier"),
    [
        ("Just a moment...", "", BarrierType.CLOUDFLARE_CHALLENGE),
        ("Attention Required! | Cloudflare", "", BarrierType.CLOUDFLARE_CHALLENGE),
        ("Verify you are human", "", BarrierType.CLOUDFLARE_CHALLENGE),
        (
            "example.com",
            '- iframe "Widget containing a Cloudflare security challenge"',
            BarrierType.CLOUDFLARE_CHALLENGE,
        ),
        ("example.com", '- checkbox "Verify you are human"', BarrierType.CLOUDFLARE_CHALLENGE),
        ("Sign up", '- iframe "reCAPTCHA"', BarrierType.RECAPTCHA),
        ("Sign up", '- checkbox "I\'m not a robot"', BarrierType.RECAPTCHA),
        (
            "Sign up",
            '- iframe "Widget containing checkbox for hCaptcha security challenge"',
            BarrierType.HCAPTCHA,
        ),
        ("Sign up", '- checkbox "I am human"', BarrierType.HCAPTCHA),
    ],
)
@pytest.mark.anyio
async def test_strong_captcha_signals_stop_through_page_state(
    title: str, aria: str, barrier: BarrierType
) -> None:
    page = PageState(url="/user/sign_up", title=title, aria_excerpt=aria)
    result = check_barrier(page)
    assert result.should_stop is True
    assert result.barrier_type == barrier

    decision = await PolicyService().check_action(_register_step(), page)
    assert decision.verdict == "stop"
    assert decision.reason == "captcha"
