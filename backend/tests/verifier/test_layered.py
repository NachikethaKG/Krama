"""LayeredVerifier: the agreed definition of "verified".

See docs/research/phase-1-together-verified-definition.md.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from playwright.async_api import Page

from app.contracts_gen.common_schema import Action, ExpectedState, Target
from app.llm import LLMAttempt
from app.ports.models import ObservedState
from app.verifier import LayeredVerifier, NetworkCall, StepEvidence, VisionVerdict

pytestmark = pytest.mark.anyio

FORM = """- main:
  - heading "New Repository" [level=1]
  - textbox "Repository Name *": policy-fixture
  - button "Create Repository"
"""
# The duplicate-name case from the research: every action "worked", nothing was created.
FORM_WITH_ERROR = FORM + "  - paragraph: The repository name is already used.\n"
REPO_PAGE = """- main:
  - heading "demo / demo-repo" [level=1]
  - link "demo-repo"
"""
TITLE = "New Repository - Gitea: Git with a cup of tea"
CREATE = Target(role="button", name="Create Repository")


def state(url: str, aria: str = "", title: str = TITLE) -> ObservedState:
    return ObservedState(url=url, title=title, aria_excerpt=aria, captured_at=datetime.now(UTC))


def evidence(
    action: str = "click",
    target: Target = CREATE,
    before: ObservedState | None = None,
    after: ObservedState | None = None,
    value: str | None = None,
    network: list[NetworkCall] | None = None,
) -> StepEvidence:
    return StepEvidence(
        action=Action(type=action, value=value),
        target=target,
        instruction_text="Click Create Repository.",
        before=before if before is not None else state("/repo/create", FORM),
        after=after if after is not None else state("/repo/create", FORM_WITH_ERROR),
        network=network or [],
    )


async def result(expected: dict[str, Any], ev: StepEvidence, **kw: Any) -> tuple[str, float, list[str]]:
    out = await LayeredVerifier(**kw).verify(ExpectedState.model_validate(expected), ev)
    v = out.verification
    return v.result, v.confidence, list(v.method)


# --- the research table: a create that silently did nothing must never verify --------------------------


@pytest.mark.parametrize(
    "expected",
    [
        {"title_contains": "Gitea"},  # true on every Gitea page
        {"visible": [{"role": "button", "name": "Create Repository"}]},  # already there before the click
        {"absent": [{"role": "text", "name": "The repository name is already used"}]},  # vacuous: wrong role
    ],
)
async def test_weak_signals_no_longer_verify_a_step_that_did_nothing(expected: dict[str, Any]) -> None:
    assert (await result(expected, evidence()))[0] == "skipped"


@pytest.mark.parametrize(
    "expected",
    [
        {"absent": [{"role": "paragraph", "name": "The repository name is already used"}]},
        {"url_matches": "^/demo/policy-fixture$"},
        {"visible": [{"role": "link", "name": "policy-fixture"}]},
    ],
)
async def test_strong_signals_fail_it(expected: dict[str, Any]) -> None:
    assert (await result(expected, evidence()))[0] == "failed"


async def test_a_real_create_verifies_through_the_new_url() -> None:
    ev = evidence(after=state("/demo/demo-repo", REPO_PAGE))

    assert await result({"url_matches": "^/demo/demo-repo$"}, ev) == ("verified", 1.0, ["url"])


# --- effect signals per action type --------------------------------------------------------------------


async def test_a_click_whose_url_was_already_right_proves_nothing() -> None:
    ev = evidence(after=state("/repo/create", FORM))  # clicked, but nothing changed

    assert (await result({"url_matches": "^/repo/create$"}, ev))[0] == "skipped"


async def test_navigate_counts_even_if_the_url_was_already_right() -> None:
    ev = evidence("navigate", Target(), value="/repo/create", after=state("/repo/create", FORM))

    assert (await result({"url_matches": "^/repo/create$"}, ev))[0] == "verified"


async def test_a_new_element_after_a_click_is_an_effect() -> None:
    menu = FORM + '  - menuitem "New Migration"\n'
    ev = evidence(after=state("/repo/create", menu))

    assert (await result({"visible": [{"role": "menuitem", "name": "New Migration"}]}, ev))[0] == "verified"


async def test_fill_is_proven_by_the_exact_value() -> None:
    box = Target(role="textbox", name="Repository Name")
    expected = {"field_values": [{"role": "textbox", "name": "Repository Name", "value": "policy-fixture"}]}

    assert (
        await result(
            expected, evidence("fill", box, value="policy-fixture", after=state("/repo/create", FORM))
        )
    )[0] == "verified"
    wrong = {"field_values": [{"role": "textbox", "name": "Repository Name", "value": "other"}]}
    assert (await result(wrong, evidence("fill", box, value="other", after=state("/repo/create", FORM))))[
        0
    ] == "failed"


async def test_a_secret_field_is_compared_masked_never_by_value() -> None:
    page = '- main:\n  - textbox "Password *": ***\n'
    pw = Target(role="textbox", name="Password")
    expected = {"field_values": [{"role": "textbox", "name": "Password", "value": "hunter2"}]}

    ev = evidence("fill", pw, value="hunter2", before=state("/login", '- main:\n  - textbox "Password *"\n'),
                  after=state("/login", page))  # fmt: skip
    assert (await result(expected, ev))[0] == "verified"


async def test_ticking_a_checkbox_is_proven_by_checked() -> None:
    box = Target(role="checkbox", name="Initialize Repository")
    after = state("/repo/create", FORM + '  - checkbox "Initialize Repository" [checked]\n')

    assert (
        await result(
            {"checked": [{"role": "checkbox", "name": "Initialize Repository"}]},
            evidence(target=box, after=after),
        )
    )[0] == "verified"


async def test_absent_and_title_together_still_prove_nothing() -> None:
    ev = evidence(after=state("/repo/create", FORM))
    expected = {"title_contains": "New Repository", "absent": [{"role": "paragraph", "name": "already used"}]}

    assert (await result(expected, ev))[0] == "skipped"


async def test_an_unreadable_page_is_skipped_not_verified() -> None:
    ev = evidence(after=state("/demo/demo-repo", ""))  # no ARIA snapshot captured
    expected = {"url_matches": "^/demo/demo-repo$", "visible": [{"role": "link", "name": "demo-repo"}]}

    assert await result(expected, ev) == ("skipped", 0.5, ["url", "aria"])


# --- network ----------------------------------------------------------------------------------------


async def test_an_accepted_post_is_an_effect_at_0_9() -> None:
    post = NetworkCall(method="POST", path="/repo/create", status=303, resource_type="document")
    ev = evidence(after=state("/repo/create", FORM), network=[post])

    assert await result({"title_contains": "Gitea"}, ev) == ("verified", 0.9, ["dom", "network"])


async def test_a_form_post_answered_with_200_is_not_an_effect() -> None:
    # Real Gitea re-renders the form with 200 when it refuses a create (tests/runs: duplicate name).
    post = NetworkCall(method="POST", path="/repo/create", status=200, resource_type="document")
    ev = evidence(after=state("/repo/create", FORM_WITH_ERROR), network=[post])

    assert (await result({"title_contains": "Gitea"}, ev))[0] == "skipped"


async def test_a_refused_post_fails_the_step() -> None:
    post = NetworkCall(method="POST", path="/repo/create", status=500, resource_type="document")
    ev = evidence(after=state("/demo/demo-repo", REPO_PAGE), network=[post])

    assert (await result({"url_matches": "^/demo/demo-repo$"}, ev))[0] == "failed"


async def test_the_threshold_decides_whether_network_alone_is_enough() -> None:
    post = NetworkCall(method="POST", path="/repo/create", status=200, resource_type="xhr")
    ev = evidence(after=state("/repo/create", FORM), network=[post])

    assert (await result({"title_contains": "Gitea"}, ev, threshold=0.95))[0] == "skipped"


# --- vision -------------------------------------------------------------------------------------------


class ScriptedJudge:
    def __init__(self, holds: bool | None) -> None:
        self.holds = holds
        self.calls = 0

    async def judge(self, page: Page, expected: ExpectedState, instruction: str) -> VisionVerdict:
        self.calls += 1
        attempt = LLMAttempt(model="scripted", status="ok", latency_ms=0)
        return VisionVerdict(holds=self.holds, reason="scripted", attempts=[attempt])


PAGE: Any = object()


async def test_vision_only_runs_when_asked_and_never_verifies_alone() -> None:
    judge = ScriptedJudge(holds=True)
    verifier = LayeredVerifier(judge)
    expected = ExpectedState(title_contains="Gitea")

    cheap = await verifier.verify(expected, evidence())
    assert judge.calls == 0 and cheap.verification.result == "skipped"

    looked = await verifier.verify(expected, evidence(), page=PAGE, use_vision=True)
    assert judge.calls == 1
    assert looked.verification.result == "skipped"  # 0.7 < 0.8: a human decides
    assert looked.verification.confidence == 0.7 and "vision" in looked.verification.method
    assert len(looked.llm_attempts) == 1


async def test_vision_is_not_asked_about_steps_that_already_failed_or_verified() -> None:
    judge = ScriptedJudge(holds=False)
    verifier = LayeredVerifier(judge)

    await verifier.verify(ExpectedState(url_matches="^/demo/x$"), evidence(), page=PAGE, use_vision=True)
    ok = evidence(after=state("/demo/demo-repo", REPO_PAGE))
    await verifier.verify(ExpectedState(url_matches="^/demo/demo-repo$"), ok, page=PAGE, use_vision=True)

    assert judge.calls == 0


async def test_a_vision_disagreement_is_shown_to_the_human_not_turned_into_a_failure() -> None:
    out = await LayeredVerifier(ScriptedJudge(holds=False)).verify(
        ExpectedState(title_contains="Gitea"), evidence(), page=PAGE, use_vision=True
    )

    assert out.verification.result == "skipped"
    assert any(c.kind == "vision" and "does NOT" in c.detail for c in out.checks)
