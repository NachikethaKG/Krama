"""Scripted fakes for every port, so each side can test without the other's real implementation."""

import hashlib
from collections import deque
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from playwright.async_api import Page

from app.ports.artifacts import ArtifactStore
from app.ports.models import (
    ArtifactContentType,
    ArtifactNotFoundError,
    ArtifactRef,
    ObservedState,
    PageState,
    PlanDraft,
    PolicyDecision,
    RecordingRef,
    Risk,
    RiskReport,
    StepRef,
    StepRisk,
    StoredArtifact,
    validate_artifact_key,
)
from app.ports.narration import (
    NarrationClip,
    NarrationError,
    NarrationErrorReason,
    NarrationLine,
    NarrationManifest,
    Narrator,
    WordTiming,
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


class FakeArtifactStore:
    """Keeps artifacts in memory. Checks keys exactly like a real store, so unsafe keys fail in tests too."""

    def __init__(self) -> None:
        self.artifacts: dict[str, StoredArtifact] = {}

    async def put(self, key: str, data: bytes, content_type: ArtifactContentType) -> ArtifactRef:
        ref = ArtifactRef(key=validate_artifact_key(key), content_type=content_type, size_bytes=len(data))
        self.artifacts[key] = StoredArtifact(ref=ref, data=data)
        return ref

    async def get(self, key: str) -> StoredArtifact:
        try:
            return self.artifacts[validate_artifact_key(key)]
        except KeyError:
            raise ArtifactNotFoundError(key) from None

    async def exists(self, key: str) -> bool:
        return validate_artifact_key(key) in self.artifacts


class FakeNarrator:
    """Deterministic narration without audio: every character takes `ms_per_char`, words get their share.

    Nothing is stored; `audio_key` points where the real narrator would put the clip. Pass `fail` to make
    every call raise NarrationError with that reason.
    """

    voice = "fake"
    sample_rate = 22050

    def __init__(self, ms_per_char: int = 60, fail: NarrationErrorReason | None = None) -> None:
        self.ms_per_char = ms_per_char
        self.fail = fail
        self.calls: list[list[NarrationLine]] = []

    async def narrate(self, lines: Sequence[NarrationLine]) -> NarrationManifest:
        self.calls.append(list(lines))
        if self.fail is not None:
            raise NarrationError(self.fail, f"fake narrator told to fail: {self.fail}")
        seqs = [line.step_seq for line in lines]
        if seqs != sorted(set(seqs)):
            raise ValueError(f"step_seq must be unique and increasing, got {seqs}")
        return NarrationManifest(
            voice=self.voice, sample_rate=self.sample_rate, clips=tuple(map(self._clip, lines))
        )

    def _clip(self, line: NarrationLine) -> NarrationClip:
        sha = hashlib.sha256(line.text.encode("utf-8")).hexdigest()
        words: list[WordTiming] = []
        t = 0
        for word in line.text.split():
            words.append(WordTiming(word=word, start_ms=t, end_ms=t + len(word) * self.ms_per_char))
            t += (len(word) + 1) * self.ms_per_char  # the space after a word is a short pause
        duration = max(t - self.ms_per_char, 0)
        return NarrationClip(
            step_seq=line.step_seq,
            text_sha256=sha,
            audio_key=f"narration/{self.voice}/{sha}.wav",
            duration_ms=duration,
            words=tuple(words),
        )


# Typed conformance: strict mypy fails here if a fake drifts from its port.
_observer: Observer = FakeObserver()
_policy: Policy = FakePolicy()
_artifacts: ArtifactStore = FakeArtifactStore()
_narrator: Narrator = FakeNarrator()
