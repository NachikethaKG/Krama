"""Sensitive sites are refused (ADR 0012, #478)."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from app.policy.sites import refusal, sensitive_site


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        ("https://www.paypal.com/signin", "payments"),
        ("https://checkout.stripe.com/x", "payments"),
        ("https://netbanking.hdfcbank.com/", "banking"),
        ("https://www.mybank.example/", "banking"),
        ("https://onlinebanking.example.org/", "banking"),
        ("https://pay.example.com/", "payments"),
        ("https://www.irs.gov/", "government identity"),
        ("https://myaadhaar.uidai.gov.in/", "government identity"),
        ("https://www.gov.uk/apply", "government identity"),
        ("https://patient.example-hospital.org/", "health"),
    ],
)
def test_sensitive_sites_are_named(url: str, kind: str) -> None:
    assert sensitive_site(url) == kind
    message = refusal(url)
    assert message is not None and kind in message


@pytest.mark.parametrize(
    "url",
    [
        "https://en.wikipedia.org/wiki/Main_Page",
        "https://www.openstreetmap.org/",
        "https://demo.playwright.dev/todomvc",
        "https://docs.python.org/3/",
        "https://github.com/",
        "http://localhost:3001",
        "https://bankstatement-tutorials.example.com/",  # "bank" inside a longer word is not a bank
        "https://paypalfans.example/",
        "",
    ],
)
def test_ordinary_sites_are_allowed(url: str) -> None:
    assert sensitive_site(url) is None and refusal(url) is None


def test_no_exit_gate_site_is_refused() -> None:
    # The Phase 7 gate's sites (#481) must be ones Krama may work on (AGENTS.md §4).
    gate = Path(__file__).resolve().parents[3] / "benchmarks" / "tasks" / "real-sites" / "gate.yaml"
    targets = [t["target"] for t in yaml.safe_load(gate.read_text(encoding="utf-8"))["tasks"]]
    assert len(targets) == 24
    assert [t for t in targets if refusal(t)] == []
