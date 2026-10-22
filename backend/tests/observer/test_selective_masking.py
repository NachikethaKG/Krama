"""Unit and integration tests for selective input masking in rrweb recording (Issue #271).

Verifies that ordinary workflow inputs (e.g. repository name, issue title, description)
remain visible in tutorial recordings while sensitive inputs (passwords, tokens, credit
cards, OTP, and email/tel PII) are masked.
"""

from __future__ import annotations

import json

import pytest
from playwright.async_api import Page

from app.observer.observer import PageObserver
from app.observer.recorder import get_rrweb_init_script
from app.observer.rrweb import RRWebRecorder
from app.ports.fakes import FakeArtifactStore
from app.ports.models import RecordingRef

pytestmark = pytest.mark.anyio

FIXTURE_FORM_HTML = """<!DOCTYPE html>
<html>
<head><title>Form Fixture - Krama Privacy Test</title></head>
<body>
  <div role="main">
    <h1>Create Repository & Configuration</h1>
    <form id="test-form">
      <!-- Non-sensitive workflow inputs -->
      <label for="repo_name">Repository Name *</label>
      <input id="repo_name" name="repo_name" type="text" value="krama-awesome-tool" />

      <label for="issue_title">Issue Title</label>
      <input id="issue_title" name="issue_title" type="text" value="Feature: add dark mode support" />

      <label for="branch_name">Branch Name</label>
      <input id="branch_name" name="branch_name" type="text" value="feat/user-settings" />

      <label for="description">Description</label>
      <textarea id="description" name="description">Walkthrough guide for new contributors.</textarea>

      <!-- Sensitive inputs: Passwords -->
      <label for="pwd">Password</label>
      <input id="pwd" name="password" type="password" value="SuperSecretP@ssword999!" />

      <label for="text_pwd">Plain Text Passcode Field</label>
      <input id="text_pwd" name="passphrase" type="text" value="correct-horse-battery-staple" />

      <!-- Sensitive inputs: Tokens / API Keys -->
      <label for="token">Personal Access Token</label>
      <input id="token" name="user_token" type="text" value="ghp_1234567890abcdef1234567890abcdef123456" />

      <label for="api_key">API Secret Key</label>
      <input id="api_key" type="text" aria-label="API Key" value="sk-abcdef1234567890abcdef123456" />

      <!-- Sensitive inputs: Financial / Cards -->
      <label for="card">Credit Card Number</label>
      <input id="card" name="card_number" autocomplete="cc-number" type="text" value="4111222233334444" />

      <label for="cvv">CVV</label>
      <input id="cvv" name="cvv" type="text" value="987" />

      <!-- Sensitive inputs: OTP / Two-Factor -->
      <label for="otp">One-Time Password</label>
      <input id="otp" name="otp_code" autocomplete="one-time-code" type="text" value="654321" />

      <!-- Sensitive inputs: Contact PII -->
      <label for="email">Account Email</label>
      <input id="email" name="user_email" type="email" value="developer@krama.dev" />

      <label for="tel">Phone Number</label>
      <input id="tel" name="phone_number" type="tel" value="+15551234567" />

      <!-- Sensitive inputs: Explicit Privacy Class -->
      <div class="krama-mask-text">
        <label for="secret_note">Confidential Internal Code</label>
        <input id="secret_note" type="text" value="classified-internal-code-777" />
      </div>

      <button type="submit">Submit</button>
    </form>
  </div>
</body>
</html>"""


def test_rrweb_init_script_contains_masking_heuristic() -> None:
    """Verify that rrweb init script contains selective masking logic."""
    script = get_rrweb_init_script()
    assert "maskInputFn" in script
    assert "isSensitiveElement" in script
    assert "SENSITIVE_ATTR_REGEX" in script
    assert "SENSITIVE_TYPE_REGEX" in script


async def test_selective_input_masking_preserves_benign_values_and_masks_sensitive(
    mock_gitea_page: Page,
) -> None:
    """Verify that benign fields are unmasked in events while sensitive fields are asterisks."""
    await mock_gitea_page.route(
        "http://gitea.local/privacy-fixture",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html; charset=utf-8",
            body=FIXTURE_FORM_HTML,
        ),
    )

    recorder = RRWebRecorder()
    await recorder.start(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/privacy-fixture")

    # Mutate benign fields with fresh values
    await mock_gitea_page.fill("#repo_name", "my-renamed-project")
    await mock_gitea_page.fill("#issue_title", "Bug: fix navigation bar overflow")
    await mock_gitea_page.fill("#description", "Updated markdown commentary for tutorial step.")

    # Mutate sensitive fields with fresh values
    await mock_gitea_page.fill("#pwd", "NewlyUpdatedSecretPass!")
    await mock_gitea_page.fill("#token", "ghp_updatedSecretToken999999999999999999")
    await mock_gitea_page.fill("#card", "5555666677778888")
    await mock_gitea_page.fill("#otp", "112233")
    await mock_gitea_page.fill("#email", "alice_new@example.org")
    await mock_gitea_page.fill("#secret_note", "dynamic-secret-payload-999")

    events = await recorder.stop()
    events_json = json.dumps(events)

    # 1. Assert all benign values are preserved in the recorded rrweb stream
    benign_values = [
        "krama-awesome-tool",
        "my-renamed-project",
        "Feature: add dark mode support",
        "Bug: fix navigation bar overflow",
        "feat/user-settings",
        "Walkthrough guide for new contributors.",
        "Updated markdown commentary for tutorial step.",
    ]
    for val in benign_values:
        assert val in events_json, f"Benign value '{val}' must be preserved in rrweb recording!"

    # 2. Assert all sensitive values are masked (never appear in rrweb stream)
    sensitive_values = [
        "SuperSecretP@ssword999!",
        "NewlyUpdatedSecretPass!",
        "correct-horse-battery-staple",
        "ghp_1234567890abcdef1234567890abcdef123456",
        "ghp_updatedSecretToken999999999999999999",
        "sk-abcdef1234567890abcdef123456",
        "4111222233334444",
        "5555666677778888",
        "987",
        "654321",
        "112233",
        "developer@krama.dev",
        "alice_new@example.org",
        "+15551234567",
        "classified-internal-code-777",
        "dynamic-secret-payload-999",
    ]
    for secret in sensitive_values:
        assert secret not in events_json, f"Sensitive secret '{secret}' must NOT be in rrweb recording!"


async def test_stored_recording_artifact_contains_no_secrets(
    mock_gitea_page: Page,
) -> None:
    """Verify that stored artifact files on disk satisfy Phase 3 exit criteria (no credentials)."""
    await mock_gitea_page.route(
        "http://gitea.local/privacy-fixture",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html; charset=utf-8",
            body=FIXTURE_FORM_HTML,
        ),
    )

    store = FakeArtifactStore()
    observer = PageObserver(artifact_store=store, run_id="selective-mask-run")

    await observer.start_recording(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/privacy-fixture")

    # Enter benign & sensitive data
    await mock_gitea_page.fill("#repo_name", "verified-open-repo")
    await mock_gitea_page.fill("#pwd", "SuperSecretArtifactPassword!")
    await mock_gitea_page.fill("#token", "ghp_ArtifactToken99999999999999999999")

    rec_ref: RecordingRef = await observer.stop_recording()

    assert rec_ref.path in store.artifacts
    raw_data = store.artifacts[rec_ref.path].data
    stored_json = raw_data.decode("utf-8")

    # Benign repo name is visible
    assert "verified-open-repo" in stored_json
    # Secrets are completely absent from stored artifact
    assert "SuperSecretArtifactPassword!" not in stored_json
    assert "ghp_ArtifactToken99999999999999999999" not in stored_json
    assert "SuperSecretP@ssword999!" not in stored_json
