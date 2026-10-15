"""End-to-end secret leak proof tests across rrweb recordings, screenshots, observations, and LLM prompts."""

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from playwright.async_api import Page

from app.observer.observer import PageObserver
from app.policy.masking import mask_prompt, mask_text
from app.policy.service import PolicyService
from app.ports.fakes import FakeArtifactStore
from app.ports.models import ObservedState

pytestmark = pytest.mark.anyio

LOGIN_TEST_PAGE_HTML = """<!DOCTYPE html>
<html>
<head><title>Sign In - Krama Test</title></head>
<body>
  <div role="main">
    <h1>Sign In</h1>
    <form id="login-form">
      <label for="username">Username</label>
      <input id="username" name="user_name" type="text" value="alice" />

      <label for="password">Password</label>
      <input id="password" name="password" type="password" value="SuperSecretP@ssword123!" />

      <div class="krama-mask-text">SecretKey: ghp_1234567890abcdef123456</div>
      <button id="login-btn" type="submit">Log In</button>
    </form>
  </div>
</body>
</html>"""


async def test_end_to_end_secret_leak_proof(mock_gitea_page: Page, tmp_path: Path) -> None:
    """Verify that sensitive values never appear in stored screenshots, rrweb JSON,
    observed_state, or LLM prompts.
    """
    secret_password = "SecretP@ssword999"
    default_secret = "SuperSecretP@ssword123!"

    # 1. Route test login page
    await mock_gitea_page.route(
        "http://gitea.local/login-test",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html; charset=utf-8",
            body=LOGIN_TEST_PAGE_HTML,
        ),
    )
    await mock_gitea_page.goto("http://gitea.local/login-test")

    store = FakeArtifactStore()
    observer = PageObserver(artifact_store=store, run_id="leak-test-run")

    # 2. Start session recording
    await observer.start_recording(mock_gitea_page)

    # 3. Type sensitive password value into password input field
    pwd_loc = mock_gitea_page.locator("#password")
    await pwd_loc.click()
    await pwd_loc.fill(secret_password)

    # 4. Capture observation
    obs = await observer.capture(mock_gitea_page, step_id="1", run_id="leak-test-run")

    # 5. Stop session recording and persist rrweb events
    rec_ref = await observer.stop_recording()

    # -------------------------------------------------------------------------
    # Verification 1: Stored Screenshot (Pixel bounding box blur & metadata)
    # -------------------------------------------------------------------------
    assert obs.screenshot is not None
    assert isinstance(obs.screenshot, bytes)
    assert len(obs.screenshot) > 0

    # Ensure plaintext secret never appears in screenshot bytes / metadata chunks
    assert secret_password.encode("utf-8") not in obs.screenshot
    assert default_secret.encode("utf-8") not in obs.screenshot

    # Verify that the password input bounding box was blurred
    pwd_box = await pwd_loc.bounding_box()
    assert pwd_box is not None

    # Compare with raw unmasked screenshot of the page
    raw_screenshot = await mock_gitea_page.screenshot(type="png", animations="disabled")
    orig_img = Image.open(BytesIO(raw_screenshot)).convert("RGB")
    blurred_img = Image.open(BytesIO(obs.screenshot)).convert("RGB")

    bx = round(pwd_box["x"])
    by = round(pwd_box["y"])
    bw = round(pwd_box["width"])
    bh = round(pwd_box["height"])

    # Pixel bounding box must be altered by the Gaussian blur
    mutations = 0
    for x in range(bx, bx + bw):
        for y in range(by, by + bh):
            if orig_img.getpixel((x, y)) != blurred_img.getpixel((x, y)):
                mutations += 1
    assert mutations > 20, "Pixels within password input bounding box should be modified by blur"

    # -------------------------------------------------------------------------
    # Verification 2: Stored rrweb JSON Payload
    # -------------------------------------------------------------------------
    assert rec_ref.path in store.artifacts
    rrweb_bytes = store.artifacts[rec_ref.path].data
    rrweb_json = rrweb_bytes.decode("utf-8")

    assert secret_password not in rrweb_json
    assert default_secret not in rrweb_json

    # -------------------------------------------------------------------------
    # Verification 3: Stored observed_state / execution logs
    # -------------------------------------------------------------------------
    observed_state = ObservedState(
        url=obs.url,
        title=obs.title,
        headings=obs.headings,
        aria_excerpt=obs.aria_excerpt,
        screenshot_path=obs.screenshot_path,
        captured_at=obs.captured_at,
    )
    observed_state_dump = observed_state.model_dump_json()
    assert secret_password not in observed_state_dump
    assert default_secret not in observed_state_dump

    obs_dict_dump = json.dumps(obs.model_dump(mode="json", exclude={"screenshot"}))
    assert secret_password not in obs_dict_dump
    assert default_secret not in obs_dict_dump

    # -------------------------------------------------------------------------
    # Verification 4: Policy Port Masking
    # -------------------------------------------------------------------------
    policy_service = PolicyService()
    masked_observed = policy_service.mask(obs)
    assert isinstance(masked_observed, ObservedState)
    masked_dump = masked_observed.model_dump_json()

    assert secret_password not in masked_dump
    assert default_secret not in masked_dump

    # -------------------------------------------------------------------------
    # Verification 5: Prepared LLM Prompt Payload
    # -------------------------------------------------------------------------
    llm_prompt = {
        "role": "user",
        "action": f"fill 'input#password' '{secret_password}'",
        "observed_aria": obs.aria_snapshot,
    }
    sanitized_prompt = mask_prompt(llm_prompt)
    prompt_json = json.dumps(sanitized_prompt)

    assert secret_password not in prompt_json
    assert default_secret not in prompt_json
    assert "[REDACTED]" in prompt_json


def test_leak_proof_offline_simulated() -> None:
    """Offline leak test verifying regex and policy masking without browser dependency."""
    secret = "SuperSecretP@ssword123!"
    token = "ghp_1234567890abcdef123456"

    # 1. String masking
    text = f"Action: fill 'input[name=\"password\"]' '{secret}' with auth token {token}"
    masked = mask_text(text)
    assert secret not in masked
    assert token not in masked
    assert "[REDACTED]" in masked

    # 2. Observed state masking
    policy = PolicyService()
    observed = ObservedState(
        url=f"/login?auth_token={token}",
        title=f"Login page password={secret}",
        headings=["Sign In", f"Your token is {token}"],
        aria_excerpt=f'- textbox "Password": {secret}',
        captured_at=datetime.now(UTC),
    )
    result = policy.mask(observed)
    dump = result.model_dump_json()
    assert secret not in dump
    assert token not in dump
    assert "[REDACTED]" in dump

    # 3. Prompt payload dictionary
    prompt_payload = {
        "messages": [
            {"role": "system", "content": "You are a helpful agent."},
            {"role": "user", "content": f"Please enter password: {secret}"},
        ],
        "credentials": {
            "token": token,
            "password": secret,
        },
    }
    sanitized_prompt = mask_prompt(prompt_payload)
    prompt_str = json.dumps(sanitized_prompt)
    assert secret not in prompt_str
    assert token not in prompt_str
    assert "[REDACTED]" in prompt_str
