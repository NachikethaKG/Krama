import re
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.contracts_gen.common_schema import ElementRef, ExpectedState, VerificationMethod
from app.contracts_gen.step_schema import StepVerification
from app.ports.models import ObservedState
from app.verifier.aria import AriaNode, parse_aria_snapshot

type CheckKind = Literal["url_matches", "title_contains", "visible", "absent", "field_value", "checked"]


class Check(BaseModel):
    """One condition of an `expected_state` and how it went. `passed=None` means it couldn't be checked."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CheckKind
    expected: str
    passed: bool | None
    detail: str


class VerificationOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verification: StepVerification
    checks: list[Check]

    @property
    def verified(self) -> bool:
        return self.verification.result == "verified"

    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.passed is False]


class Verifier(Protocol):
    def verify(self, expected: ExpectedState, observed: ObservedState) -> VerificationOutcome: ...


class RuleVerifier:
    """Verifier v0: compares `expected_state` with what the observer captured, using cheap, exact signals.

    - `url_matches`: regex search on the URL **path** (method `url`)
    - `title_contains`: substring of the page title (method `dom`)
    - `visible` / `absent` / `field_values` / `checked`: the ARIA snapshot (method `aria`). Names match as
      a case-insensitive substring, like Playwright's role locators ("Repository Name" finds
      "Repository Name *").

    Result: `failed` if any condition fails (confidence 1.0: these checks are exact), `skipped` if a condition
    couldn't be checked (e.g. no ARIA snapshot) and none failed (confidence 0.5), otherwise `verified` (1.0).
    """

    def verify(self, expected: ExpectedState, observed: ObservedState) -> VerificationOutcome:
        checks: list[Check] = []
        methods: list[VerificationMethod] = []

        if expected.url_matches is not None:
            methods.append("url")
            checks.append(_check_url(expected.url_matches, observed.url))
        if expected.title_contains is not None:
            methods.append("dom")
            ok = expected.title_contains.lower() in observed.title.lower()
            checks.append(
                Check(
                    kind="title_contains",
                    expected=expected.title_contains,
                    passed=ok,
                    detail=f"title is {observed.title!r}",
                )
            )

        aria_conditions = [expected.visible, expected.absent, expected.field_values, expected.checked]
        if any(aria_conditions):
            methods.append("aria")
            nodes = parse_aria_snapshot(observed.aria_excerpt) if observed.aria_excerpt.strip() else None
            checks += _aria_checks(expected, nodes)

        if not checks:
            # The planner rejects empty expected states (the generated models don't enforce minProperties).
            checks.append(
                Check(kind="url_matches", expected="", passed=None, detail="expected_state has no conditions")
            )
            methods.append("url")

        if any(c.passed is False for c in checks):
            result, confidence = "failed", 1.0
        elif any(c.passed is None for c in checks):
            result, confidence = "skipped", 0.5
        else:
            result, confidence = "verified", 1.0
        verification = StepVerification(result=result, method=methods, confidence=confidence)
        return VerificationOutcome(verification=verification, checks=checks)


class ScriptedVerifier:
    """Returns the outcomes it was given, in order (the mock seam for executor and replan tests)."""

    def __init__(self, outcomes: Sequence[VerificationOutcome]) -> None:
        self._outcomes = list(outcomes)

    def verify(self, expected: ExpectedState, observed: ObservedState) -> VerificationOutcome:
        if not self._outcomes:
            raise AssertionError("ScriptedVerifier ran out of outcomes")
        return self._outcomes.pop(0)


def _check_url(pattern: str, path: str) -> Check:
    try:
        ok = re.search(pattern, path) is not None
    except re.error as e:
        return Check(kind="url_matches", expected=pattern, passed=False, detail=f"invalid regex: {e}")
    return Check(kind="url_matches", expected=pattern, passed=ok, detail=f"path is {path!r}")


def _find(nodes: list[AriaNode], ref: ElementRef) -> list[AriaNode]:
    name = ref.name.lower()
    return [n for n in nodes if n.role == ref.role and name in n.label().lower()]


def _ref(ref: ElementRef) -> str:
    return f'{ref.role} "{ref.name}"'


def _aria_checks(expected: ExpectedState, nodes: list[AriaNode] | None) -> list[Check]:
    if nodes is None:
        refs = [
            *(("visible", _ref(r)) for r in expected.visible or []),
            *(("absent", _ref(r)) for r in expected.absent or []),
            *(
                ("field_value", _ref(ElementRef(role=f.role, name=f.name)))
                for f in expected.field_values or []
            ),
            *(("checked", _ref(r)) for r in expected.checked or []),
        ]
        return [Check(kind=k, expected=e, passed=None, detail="no ARIA snapshot captured") for k, e in refs]

    checks: list[Check] = []
    for ref in expected.visible or []:
        found = _find(nodes, ref)
        checks.append(
            Check(
                kind="visible",
                expected=_ref(ref),
                passed=bool(found),
                detail=f"{len(found)} matching element(s)",
            )
        )
    for ref in expected.absent or []:
        found = _find(nodes, ref)
        detail = "not present" if not found else f"present: {found[0].label()!r}"
        checks.append(Check(kind="absent", expected=_ref(ref), passed=not found, detail=detail))
    for fv in expected.field_values or []:
        found = _find(nodes, ElementRef(role=fv.role, name=fv.name))
        ok = any(n.value == fv.value for n in found)
        values = [n.value for n in found]
        detail = f"value is {values[0]!r}" if len(values) == 1 else f"{len(values)} fields, values {values!r}"
        checks.append(
            Check(
                kind="field_value",
                expected=f"{_ref(ElementRef(role=fv.role, name=fv.name))} = {fv.value!r}",
                passed=ok,
                detail=detail,
            )
        )
    for ref in expected.checked or []:
        found = _find(nodes, ref)
        ok = any(n.checked for n in found)
        detail = "not found" if not found else ("checked" if ok else "not checked")
        checks.append(Check(kind="checked", expected=_ref(ref), passed=ok, detail=detail))
    return checks
