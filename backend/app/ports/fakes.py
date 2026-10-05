"""Scripted fakes for every port, so each side can test without the other's real implementation."""

from collections import deque
from collections.abc import Iterable
from datetime import UTC, datetime

from playwright.async_api import Page

from app.ports.models import (
    ObservedState,
    PageState,
    PlanDraft,
    PolicyDecision,
    RecordingRef,
    Risk,
    RiskReport,
    StepRef,
    StepRisk,
)
from app.ports.observer import Observer
from app.ports.policy import Policy


class FakeObserver:
    """Returns scripted states in order; once they run out, a minimal state for the step."""

    def __init__(self, states: Iterable[ObservedState] = ()) -> None:
        self._states = deque(states)
        self.captured: list[StepRef] = []
        self.recording = False
        self._started_at: datetime | None = None

    async def capture(self, page: Page, step: StepRef) -> ObservedState:
        self.captured.append(step)
        if self._states:
            return self._states.popleft()
        return ObservedState(url="/", title=f"after step {step.seq}", captured_at=datetime.now(UTC))

    async def start_recording(self, page: Page) -> None:
        self.recording = True
        self._started_at = datetime.now(UTC)

    async def stop_recording(self) -> RecordingRef:
        if not self.recording or self._started_at is None:
            raise RuntimeError("stop_recording() called before start_recording()")
        self.recording = False
        return RecordingRef(
            path="fake/recording.json",
            event_count=len(self.captured),
            started_at=self._started_at,
            ended_at=datetime.now(UTC),
        )


class FakePolicy:
    """Allows everything unless told otherwise per step `seq`. `mask` returns the state unchanged."""

    def __init__(
        self,
        decisions: dict[int, PolicyDecision] | None = None,
        risks: dict[int, Risk] | None = None,
    ) -> None:
        self._decisions = decisions or {}
        self._risks = risks or {}
        self.checked: list[tuple[StepRef, PageState]] = []
        self.masked: list[ObservedState] = []

    async def assess_plan(self, plan: PlanDraft) -> RiskReport:
        return RiskReport.from_steps(
            [StepRisk(seq=s.seq, risk=self._risks.get(s.seq, "low"), reason="scripted") for s in plan.steps]
        )

    async def check_action(self, step: StepRef, page: PageState) -> PolicyDecision:
        self.checked.append((step, page))
        return self._decisions.get(step.seq, PolicyDecision(verdict="allow"))

    def mask(self, observed: ObservedState) -> ObservedState:
        self.masked.append(observed)
        return observed


# Typed conformance: strict mypy fails here if a fake drifts from its port.
_observer: Observer = FakeObserver()
_policy: Policy = FakePolicy()
