"""The Narrator port: spoken narration for the video export (Phase 5).

Implemented by `app.tts` (Vishwas, #120), called by the export job in `app.export` (Nachiketha, #126).
Decisions D3-D5 in docs/research/phase-5-decisions-alignment.md; voice and license in docs/adr/0004.

`plan_scenes` turns a manifest into scene lengths in whole video frames (D4). It lives here so the export job
can use it without importing `app.tts`.
"""

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from app.contracts_gen.tutorial_spec_schema import WordTiming
from app.ports.models import ArtifactKey, _Model

__all__ = [
    "DEFAULT_FPS",
    "HOLD_MS",
    "LEAD_IN_MS",
    "NarrationClip",
    "NarrationError",
    "NarrationErrorReason",
    "NarrationLine",
    "NarrationManifest",
    "Narrator",
    "SceneTiming",
    "WordTiming",
    "plan_scenes",
]

DEFAULT_FPS = 30
LEAD_IN_MS = 300  # the cursor starts moving, then the voice starts
HOLD_MS = 400  # silence after the voice before the next scene, same as the player's narration hold (#267)

NarrationErrorReason = Literal["worker_unavailable", "voice_missing", "synthesis_failed"]


class NarrationError(RuntimeError):
    """Narration could not be made. `reason` says why, so the export job can report it as the export error."""

    def __init__(self, reason: NarrationErrorReason, message: str) -> None:
        super().__init__(message)
        self.reason: NarrationErrorReason = reason


class NarrationLine(_Model):
    """One step to narrate: the step's instruction text (already masked if the step is sensitive)."""

    step_seq: int = Field(ge=1)
    text: str = Field(min_length=1)


class NarrationClip(_Model):
    """One step's narration: a WAV in the ArtifactStore, with word timings relative to the clip's start."""

    step_seq: int = Field(ge=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audio_key: ArtifactKey
    duration_ms: int = Field(ge=0)
    words: tuple[WordTiming, ...] = ()

    @model_validator(mode="after")
    def _words_fit(self) -> Self:
        previous_end = 0
        for w in self.words:
            if w.start_ms < previous_end or w.end_ms < w.start_ms or w.end_ms > self.duration_ms:
                raise ValueError(
                    f"word timings must be in order, not overlap and end within the clip ({w.word!r} "
                    f"{w.start_ms}-{w.end_ms} ms, clip {self.duration_ms} ms)"
                )
            previous_end = w.end_ms
        return self


class NarrationManifest(_Model):
    """Narration for a whole tutorial: one clip per narrated step, in step order."""

    voice: str = Field(min_length=1)
    sample_rate: int = Field(gt=0)
    clips: tuple[NarrationClip, ...]

    @model_validator(mode="after")
    def _one_clip_per_step(self) -> Self:
        seqs = [c.step_seq for c in self.clips]
        if seqs != sorted(set(seqs)):
            raise ValueError(f"clips must have unique step_seq in increasing order, got {seqs}")
        return self


class Narrator(Protocol):
    """Makes spoken narration for a tutorial's steps."""

    async def narrate(self, lines: Sequence[NarrationLine]) -> NarrationManifest:
        """One clip per line, in the same order. `step_seq` must be unique and increasing.

        Clips already stored for the same voice and text are reused, not made again.
        Raises NarrationError, or ValueError for duplicate or unordered `step_seq`.
        """
        ...


class SceneTiming(_Model):
    """Where one step's scene sits on the video timeline, in frames and in milliseconds.

    `start_ms` / `duration_ms` are whole milliseconds that round back to exactly `start_frame` / `frames` with
    the TutorialSpec rule `frame = round(ms / 1000 * fps)`, so they can go straight into the compiler's
    `stepDurations`.
    `words` are relative to the scene start (the clip starts at `audio_offset_ms`), ready for `wordTimings`.
    """

    step_seq: int = Field(ge=1)
    start_frame: int = Field(ge=0)
    frames: int = Field(ge=1)
    start_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=1)
    audio_key: ArtifactKey
    audio_offset_ms: int = Field(ge=0)
    words: tuple[WordTiming, ...] = ()


def plan_scenes(
    manifest: NarrationManifest,
    action_ms: Mapping[int, int],
    *,
    fps: int = DEFAULT_FPS,
    lead_in_ms: int = LEAD_IN_MS,
    hold_ms: int = HOLD_MS,
    start_frame: int = 0,
) -> tuple[SceneTiming, ...]:
    """Scene length = max(recorded action, lead-in + clip + hold), rounded UP to whole frames (decision D4).

    `action_ms` maps step_seq to the recorded action's duration (end_ms - start_ms); a missing step counts
    as 0.
    `start_frame` is where the first scene starts (e.g. after an intro card). Every scene start is computed in
    frames first and only then turned into milliseconds, so audio and video never drift apart (a ms timeline
    rounded to frames separately drifted 1 s over 60 scenes in the research check).
    """
    if fps < 1:
        raise ValueError("fps must be at least 1")
    if lead_in_ms < 0 or hold_ms < 0 or start_frame < 0:
        raise ValueError("lead_in_ms, hold_ms and start_frame must not be negative")
    scenes: list[SceneTiming] = []
    frame = start_frame
    for clip in manifest.clips:
        action = action_ms.get(clip.step_seq, 0)
        if action < 0:
            raise ValueError(f"step {clip.step_seq}: action duration must not be negative ({action} ms)")
        want_ms = max(action, lead_in_ms + clip.duration_ms + hold_ms, 1)
        frames = -(-want_ms * fps // 1000)  # ceil without floats
        start_ms = _frame_to_ms(frame, fps)
        scenes.append(
            SceneTiming(
                step_seq=clip.step_seq,
                start_frame=frame,
                frames=frames,
                start_ms=start_ms,
                duration_ms=_frame_to_ms(frame + frames, fps) - start_ms,
                audio_key=clip.audio_key,
                audio_offset_ms=lead_in_ms,
                words=tuple(
                    WordTiming(word=w.word, start_ms=w.start_ms + lead_in_ms, end_ms=w.end_ms + lead_in_ms)
                    for w in clip.words
                ),
            )
        )
        frame += frames
    return tuple(scenes)


def _frame_to_ms(frame: int, fps: int) -> int:
    """Nearest whole millisecond to a frame boundary (round half up, integers only)."""
    return (frame * 2000 + fps) // (2 * fps)
