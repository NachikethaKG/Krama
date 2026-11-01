"""Scripted fakes for every port, so each side can test without the other's real implementation."""

import asyncio
import hashlib
import tempfile
from collections import deque
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from playwright.async_api import Page

from app.contracts_gen.export_schema import Export, ExportError, ExportErrorCode
from app.contracts_gen.workflow_schema import Workflow
from app.ports.artifacts import ArtifactFiles, ArtifactStore
from app.ports.exports import (
    ExportJobInput,
    ExportNotFoundError,
    ExportQueue,
    ExportStateError,
    ExportStore,
)
from app.ports.models import (
    ArtifactContentType,
    ArtifactInfo,
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
    validate_artifact_prefix,
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
    """Keeps artifacts in memory. Checks keys exactly like a real store, so unsafe keys fail in tests too.

    Implements `ArtifactStore` and `ArtifactFiles`; `local_path` writes the bytes to a temporary folder.
    """

    def __init__(self) -> None:
        self.artifacts: dict[str, StoredArtifact] = {}
        self.modified: dict[str, datetime] = {}
        self._files: Path | None = None

    async def put(self, key: str, data: bytes, content_type: ArtifactContentType) -> ArtifactRef:
        ref = ArtifactRef(key=validate_artifact_key(key), content_type=content_type, size_bytes=len(data))
        self.artifacts[key] = StoredArtifact(ref=ref, data=data)
        self.modified[key] = datetime.now(UTC)
        return ref

    async def put_file(self, key: str, path: Path, content_type: ArtifactContentType) -> ArtifactRef:
        validate_artifact_key(key)
        return await self.put(key, await asyncio.to_thread(path.read_bytes), content_type)

    async def local_path(self, key: str) -> Path:
        data = (await self.get(key)).data
        if self._files is None:
            self._files = Path(tempfile.mkdtemp(prefix="krama-fake-artifacts-"))
        path = self._files / key
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        return path

    async def delete(self, key: str) -> bool:
        self.modified.pop(validate_artifact_key(key), None)
        return self.artifacts.pop(key, None) is not None

    async def list(self, prefix: str) -> list[ArtifactInfo]:
        validate_artifact_prefix(prefix)
        return [
            ArtifactInfo(key=k, size_bytes=a.ref.size_bytes, modified_at=self.modified[k])
            for k, a in sorted(self.artifacts.items())
            if k.startswith(prefix)
        ]

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


class FakeExportStore:
    """The `exports` table in memory, with the same status rules as the real store."""

    def __init__(self) -> None:
        self.exports: dict[UUID, Export] = {}
        self.workflows: dict[UUID, Workflow] = {}
        self.videos: dict[UUID, ArtifactRef] = {}
        self.captions: dict[UUID, ArtifactRef] = {}

    def add(self, export: Export, workflow: Workflow) -> None:
        self.exports[export.id] = export
        self.workflows[export.id] = workflow

    async def load(self, export_id: UUID) -> ExportJobInput:
        return ExportJobInput(export=self._get(export_id), workflow=self.workflows[export_id])

    async def mark_rendering(self, export_id: UUID, progress: int) -> None:
        e = self._get(export_id)
        if e.status not in ("queued", "rendering"):
            raise ExportStateError(f"export {export_id} is {e.status}")
        update: dict[str, object] = {"status": "rendering", "progress": max(e.progress, min(progress, 99))}
        if e.started_at is None:
            update["started_at"] = datetime.now(UTC)
        self.exports[export_id] = e.model_copy(update=update)

    async def mark_ready(
        self, export_id: UUID, *, video: ArtifactRef, captions: ArtifactRef | None, duration_ms: int
    ) -> None:
        e = self._get(export_id)
        if e.status != "rendering":
            raise ExportStateError(f"export {export_id} is {e.status}, not rendering")
        self.videos[export_id] = video
        if captions is not None:
            self.captions[export_id] = captions
        base = f"/api/v1/exports/{export_id}"
        self.exports[export_id] = e.model_copy(
            update={
                "status": "ready",
                "progress": 100,
                "size_bytes": video.size_bytes,
                "duration_ms": duration_ms,
                "download_url": f"{base}/download",
                "captions_url": f"{base}/captions.vtt" if captions is not None else None,
                "finished_at": datetime.now(UTC),
            }
        )

    async def mark_failed(self, export_id: UUID, code: ExportErrorCode, message: str) -> None:
        e = self._get(export_id)
        if e.status not in ("queued", "rendering"):
            raise ExportStateError(f"export {export_id} is {e.status}")
        self.exports[export_id] = e.model_copy(
            update={
                "status": "failed",
                "error": ExportError(code=code, message=message),
                "finished_at": datetime.now(UTC),
            }
        )

    def _get(self, export_id: UUID) -> Export:
        try:
            return self.exports[export_id]
        except KeyError:
            raise ExportNotFoundError(str(export_id)) from None


TINY_MP4 = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "exports" / "tiny.mp4"
"""A real 1 s, 192x108 H.264 + AAC MP4 (3.5 KB), for tests and the mock export queue."""


class FakeExportQueue:
    """Records what was enqueued. Given a store and files, it "renders" at once instead: marks the export
    rendering, stores `video` (default: the tiny fixture MP4) at `exports/<id>.mp4`, and marks it ready, or
    failed with `fail`. That lets the export API and dialog work before the real export job exists (D14)."""

    def __init__(
        self,
        store: ExportStore | None = None,
        files: ArtifactFiles | None = None,
        *,
        video: Path = TINY_MP4,
        fail: ExportErrorCode | None = None,
    ) -> None:
        self.store, self.files, self.video, self.fail = store, files, video, fail
        self.enqueued: list[UUID] = []

    async def enqueue(self, export_id: UUID) -> None:
        self.enqueued.append(export_id)
        if self.store is None or self.files is None:
            return
        await self.store.mark_rendering(export_id, 0)
        if self.fail is not None:
            await self.store.mark_failed(export_id, self.fail, f"fake export queue told to fail: {self.fail}")
            return
        ref = await self.files.put_file(f"exports/{export_id}.mp4", self.video, "video/mp4")
        await self.store.mark_ready(export_id, video=ref, captions=None, duration_ms=1000)


# Typed conformance: strict mypy fails here if a fake drifts from its port.
_observer: Observer = FakeObserver()
_policy: Policy = FakePolicy()
_artifacts: ArtifactStore = FakeArtifactStore()
_narrator: Narrator = FakeNarrator()
_artifact_files: ArtifactFiles = FakeArtifactStore()
_export_store: ExportStore = FakeExportStore()
_export_queue: ExportQueue = FakeExportQueue()
