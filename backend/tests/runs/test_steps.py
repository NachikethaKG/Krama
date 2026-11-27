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


# --- a replayed step with nothing left to do (#482) ------------------------------------------------------

BAILEY = '- heading "New Stuff by Bailey" [level=2]\n- button "Dismiss This Alert"'
TASKS = '- heading "Tasks" [level=1]\n- textbox "Add a To Do"'


def replayed(expected: dict[str, Any], page: str, error: str | None) -> tuple[PlannedStep, StepOutcome]:
    from datetime import UTC, datetime

    from app.agent.executor import ActionError, ActionResult
    from app.ports.models import ObservedState

    planned = PlannedStep.model_validate(
        step(1, {"type": "click"}, {"role": "button", "name": "Dismiss This Alert"}, "Close it.", expected)
    )
    result = ActionResult(
        action="click", ok=error is None, started_at=datetime.now(UTC), duration_ms=1, url_after="/",
        error=ActionError(code=error, message="no") if error else None,
    )  # fmt: skip
    observed = ObservedState(url="/", title="Habitica", aria_excerpt=page, captured_at=datetime.now(UTC))
    return planned, StepOutcome(
        result=result, before=None, observed=observed, verification=None, verify_attempts=0
    )


GONE = {"absent": [{"role": "heading", "name": "New Stuff by Bailey"}]}


@pytest.mark.parametrize(
    ("expected", "page", "error", "done"),
    [
        # Habitica's news popup, closed when the workflow was made; this time it never showed.
        (GONE, TASKS, "target_not_found", True),
        # The popup is there but its button wasn't found: something else is wrong.
        (GONE, BAILEY, "target_not_found", False),
        # Several matching elements: the page changed, not a popup that went away.
        (GONE, TASKS, "ambiguous_target", False),
        # A step that must make something appear is never "already done".
        ({**GONE, "visible": [{"role": "heading", "name": "Tasks"}]}, TASKS, "target_not_found", False),
        ({"url_matches": "^/$"}, TASKS, "target_not_found", False),
        # The action ran: nothing to skip.
        (GONE, TASKS, None, False),
    ],
)
def test_a_popup_that_isnt_there_is_already_done(
    expected: dict[str, Any], page: str, error: str | None, done: bool
) -> None:
    from app.runs.steps import already_done

    assert already_done(*replayed(expected, page, error)) is done
