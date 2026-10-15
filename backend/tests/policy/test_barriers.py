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
