"""act_and_verify on a real page: the before-state, network evidence and the one vision look."""

from pathlib import Path
from typing import Any

import pytest

from app.agent import ActionExecutor, PlaywrightSession, SessionConfig
from app.contracts_gen.plan_schema import PlannedStep
from app.llm import FakeProvider, FakeResponse
from app.observer import PageObserver
from app.runs.steps import StepOutcome, act_and_verify
from app.verifier import LayeredVerifier
from app.verifier.vision import GeminiVisionJudge
from tests.runs.test_runner import GOOD_PLAN, step

pytestmark = pytest.mark.anyio


async def run_step(
    site: str, tmp_path: Path, planned: dict[str, Any], verifier: LayeredVerifier, path: str = "/form"
) -> StepOutcome:
    async with PlaywrightSession(SessionConfig(base_url=site)) as session:
        await session.page.goto(path)
        return await act_and_verify(
            PlannedStep.model_validate(planned),
            ActionExecutor(session.page),
            PageObserver(artifacts_dir=tmp_path),
            verifier,
            session.page,
            verify_timeout_s=1.0,
            verify_interval_s=0.2,
        )


async def test_a_form_post_is_recorded_as_network_evidence(site: str, tmp_path: Path) -> None:
    out = await run_step(site, tmp_path, GOOD_PLAN["steps"][3], LayeredVerifier())

    assert out.verified
    assert [(c.method, c.path, c.status) for c in out.network] == [("POST", "/done", 303)]
    assert out.before is not None and out.before.url == "/form" and out.observed.url == "/done"
    assert out.verification is not None
    assert out.verification.verification.method == ["url", "aria", "network"]


async def test_an_unclear_step_gets_one_vision_look_with_a_masked_screenshot(
    site: str, tmp_path: Path
) -> None:
    llm = FakeProvider([FakeResponse(name="v", response={"holds": True, "reason": "the form is shown"})])
    # A plain link click whose only expectation is a title: no POST, no URL condition, so nothing proves it.
    weak = step(
        1,
        {"type": "click"},
        {"role": "link", "name": "New item"},
        "Click New item.",
        {"title_contains": "item"},
    )

    out = await run_step(site, tmp_path, weak, LayeredVerifier(GeminiVisionJudge(llm)), path="/")

    assert out.unclear and not out.verified
    assert out.verification is not None and out.verification.verification.confidence == 0.7
    assert len(llm.calls) == 1  # once, after the cheap layers gave up, not on every poll
    system, prompt, _schema = llm.calls[0]
    assert "UNTRUSTED" in system and "Click New item." in prompt and "title contains 'item'" in prompt
    assert llm.images[0] is not None and llm.images[0].startswith(b"\x89PNG")
