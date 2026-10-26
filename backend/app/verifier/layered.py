"""Layered verifier: cheapest reliable signal first (URL/DOM → ARIA → network), Gemini vision last.

What "verified" means (docs/research/phase-1-together-verified-definition.md, agreed in #45):
1. every expected condition passes (any failure → `failed`);
2. at least one EFFECT signal for the action type passes. For a click or key press, a condition that was
   already true before the step is not evidence that the step did anything;
3. step confidence (the best effect signal) ≥ 0.8.
Otherwise the step is `skipped`: nothing contradicts it, but nothing proves it either, so a human looks.
`title_contains` and `absent` never count as an effect on their own. Vision (0.7) can add evidence for the
human, but never verifies a step by itself.
"""

import re
from typing import Protocol

from playwright.async_api import Page
from pydantic import BaseModel, ConfigDict

from app.agent.runlog import looks_sensitive, mask_expected
from app.contracts_gen.common_schema import (
    Action,
    ElementRef,
    ExpectedState,
    FieldValue,
    Target,
    VerificationMethod,
)
from app.contracts_gen.step_schema import StepVerification
from app.llm import LLMAttempt
from app.ports.models import ObservedState
from app.verifier.aria import AriaNode, parse_aria_snapshot
from app.verifier.verifier import Check, RuleVerifier, VerificationOutcome, url_path_matches

THRESHOLD = 0.8
CONFIDENCE: dict[VerificationMethod, float] = {
    "url": 1.0,
    "dom": 1.0,
    "aria": 1.0,
    "network": 0.9,
    "vision": 0.7,
}
UNCHECKED_CONFIDENCE = 0.5
_TOGGLES = frozenset({"checkbox", "radio", "switch", "menuitemcheckbox", "menuitemradio"})
_STATE_ACTIONS = frozenset({"navigate", "fill", "select", "wait"})
"""Actions whose result is a state: if that state holds afterwards, it counts even if it held before."""


class NetworkCall(BaseModel):
    """A same-origin request that could change data (not GET), made while the step ran."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    path: str
    status: int | None
    """None if it failed without a response."""
    resource_type: str


class StepEvidence(BaseModel):
    """Everything the verifier may look at for one step."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    action: Action
    target: Target
    instruction_text: str
    before: ObservedState | None
    """Captured right before the action; None if unavailable (then nothing is ruled out as "already true")."""
    after: ObservedState
    network: list[NetworkCall] = []


class VisionVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    holds: bool | None
    """Whether the screenshot shows the expected state; None if the model couldn't tell or failed."""
    reason: str = ""
    attempts: list[LLMAttempt] = []


class VisionJudge(Protocol):
    async def judge(self, page: Page, expected: ExpectedState, instruction: str) -> VisionVerdict: ...


class StepVerifier(Protocol):
    async def verify(
        self,
        expected: ExpectedState,
        evidence: StepEvidence,
        *,
        page: Page | None = None,
        use_vision: bool = False,
    ) -> VerificationOutcome: ...


class LayeredVerifier:
    def __init__(self, vision: VisionJudge | None = None, *, threshold: float = THRESHOLD) -> None:
        self._rules = RuleVerifier()
        self._vision = vision
        self._threshold = threshold

    @property
    def has_vision(self) -> bool:
        return self._vision is not None

    async def verify(
        self,
        expected: ExpectedState,
        evidence: StepEvidence,
        *,
        page: Page | None = None,
        use_vision: bool = False,
    ) -> VerificationOutcome:
        expected = _masked_expectations(expected, evidence.target)
        checks = list(self._rules.verify(expected, evidence.after).checks)
        methods = _methods(expected)
        checks += _network_checks(evidence.network)
        if evidence.network:
            methods.append("network")

        effects = _effects(expected, evidence)
        failed = any(c.passed is False for c in checks)
        unchecked = any(c.passed is None for c in checks)
        attempts: list[LLMAttempt] = []

        if failed:
            result, confidence = "failed", 1.0
        else:
            confidence = max((CONFIDENCE[m] for m in effects), default=UNCHECKED_CONFIDENCE)
            if unchecked:
                confidence = min(confidence, UNCHECKED_CONFIDENCE)
            result = "verified" if effects and not unchecked and confidence >= self._threshold else "skipped"
            if result == "skipped" and use_vision and self._vision is not None and page is not None:
                verdict = await self._vision.judge(page, expected, evidence.instruction_text)
                attempts = verdict.attempts
                methods.append("vision")
                checks.append(_vision_check(verdict))
                if verdict.holds:
                    confidence = max(
                        confidence, CONFIDENCE["vision"]
                    )  # still below the threshold: a human looks
        verification = StepVerification(
            result=result, method=_unique(methods) or ["url"], confidence=round(confidence, 2)
        )
        effect_check = Check(
            kind="effect",
            expected="an effect signal for this action",
            passed=None if failed else bool(effects),
            detail=", ".join(effects) or "none of the passing conditions shows that the action did something",
        )
        return VerificationOutcome(
            verification=verification, checks=[*checks, effect_check], llm_attempts=attempts
        )


def _effects(expected: ExpectedState, ev: StepEvidence) -> list[VerificationMethod]:
    """The methods of the passing conditions that show this action had an effect."""
    after, before = _nodes(ev.after), _nodes(ev.before)
    kind = ev.action.type
    is_toggle = kind == "click" and (ev.target.role or "") in _TOGGLES
    state_action = kind in _STATE_ACTIONS or is_toggle
    found: list[VerificationMethod] = []

    def url_holds(path: str | None) -> bool:
        return path is not None and _url_check(expected, path)

    if expected.url_matches is not None and url_holds(ev.after.url):
        before_path = ev.before.url if ev.before else None
        if kind == "navigate" or (kind in ("click", "press") and not url_holds(before_path)):
            found.append("url")

    if after is not None:
        if kind in ("fill", "select") and expected.field_values and _all_fields(expected.field_values, after):
            found.append("aria")
        if is_toggle and expected.checked and all(_checked(r, after) for r in expected.checked):
            found.append("aria")
        if expected.visible and kind in ("click", "press", "wait"):
            new = [
                r
                for r in expected.visible
                if _present(r, after) and (state_action or not _present(r, before))
            ]
            if new:
                found.append("aria")

    if kind in ("click", "press") and any(_accepted(c) for c in ev.network):
        found.append("network")
    return _unique(found)


def _masked_expectations(expected: ExpectedState, target: Target) -> ExpectedState:
    """The observer shows *** instead of a secret field's value, so expect *** there."""
    return mask_expected(expected) if looks_sensitive(target.name) else expected


def _accepted(call: NetworkCall) -> bool:
    """A request that shows the server took the change. A form POST must be answered with a redirect: real
    Gitea answers a REFUSED create (name already used) with 200 and the form again, so 200 proves nothing
    for a page load. XHR/fetch calls report through their status, so 2xx counts there."""
    if call.status is None:
        return False
    if call.resource_type == "document":
        return 300 <= call.status < 400
    return 200 <= call.status < 400


def _network_checks(calls: list[NetworkCall]) -> list[Check]:
    """A data-changing request that the server refused (4xx/5xx) or that never got an answer is a failure.

    A request without an answer is ignored when the same request did get one: GitHub sends its "Save changes"
    PUT twice and cancels one (#89)."""
    answered = {(c.method, c.path) for c in calls if c.status is not None}
    checks = []
    for call in calls:
        if call.status is None and (call.method, call.path) in answered:
            continue
        ok = call.status is not None and call.status < 400
        detail = f"{call.status}" if call.status is not None else "no response"
        checks.append(
            Check(kind="network", expected=f"{call.method} {call.path} succeeds", passed=ok, detail=detail)
        )
    return checks


def _vision_check(verdict: VisionVerdict) -> Check:
    # Vision never fails a step on its own: a disagreement is shown to the human, who decides.
    if verdict.holds is None:
        said = "vision: could not tell"
    else:
        said = "vision: the screenshot shows the expected state" if verdict.holds else "vision: it does NOT"
    return Check(
        kind="vision",
        expected="the screenshot shows the expected state",
        passed=None,
        detail=f"{said} {verdict.reason}".strip(),
    )


def _methods(expected: ExpectedState) -> list[VerificationMethod]:
    methods: list[VerificationMethod] = []
    if expected.url_matches is not None:
        methods.append("url")
    if expected.title_contains is not None:
        methods.append("dom")
    if expected.visible or expected.absent or expected.field_values or expected.checked:
        methods.append("aria")
    return methods


def _url_check(expected: ExpectedState, path: str) -> bool:
    assert expected.url_matches is not None
    try:
        return url_path_matches(expected.url_matches, path)
    except re.error:
        return False


def _nodes(state: ObservedState | None) -> list[AriaNode] | None:
    if state is None or not state.aria_excerpt.strip():
        return None
    return parse_aria_snapshot(state.aria_excerpt)


def _matching(ref: ElementRef | FieldValue, nodes: list[AriaNode] | None) -> list[AriaNode]:
    """Same rule as the RuleVerifier: role equal, name a case-insensitive substring of the node's label."""
    name = ref.name.lower()
    return [n for n in nodes or [] if n.role == ref.role and name in n.label().lower()]


def _present(ref: ElementRef, nodes: list[AriaNode] | None) -> bool:
    return bool(_matching(ref, nodes))


def _checked(ref: ElementRef, nodes: list[AriaNode]) -> bool:
    return any(n.checked for n in _matching(ref, nodes))


def _all_fields(values: list[FieldValue], nodes: list[AriaNode]) -> bool:
    return all(any(n.value == fv.value for n in _matching(fv, nodes)) for fv in values)


def _unique[T](items: list[T]) -> list[T]:
    return list(dict.fromkeys(items))
