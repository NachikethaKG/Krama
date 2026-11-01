"""Narrator port: value types, the fake, and the scene-timing rule (decisions D3-D5, Phase 5)."""

import hashlib

import pytest
from pydantic import ValidationError

from app.ports import NarrationClip, NarrationError, NarrationLine, NarrationManifest, plan_scenes
from app.ports.fakes import FakeNarrator
from app.ports.narration import WordTiming

pytestmark = pytest.mark.anyio

SHA = "0" * 64

# The real 6-step GitHub "create label" workflow from the research check
# (docs/research/phase-5-vishwas-audio-pipeline.md): recorded action ms and ljspeech-medium clip ms per step.
LABEL_FLOW = [(5956, 1718), (486, 1057), (298, 3553), (239, 4075), (287, 5608), (352, 3878)]


def clip(seq: int, duration_ms: int, words: tuple[WordTiming, ...] = ()) -> NarrationClip:
    key = f"narration/v/{seq}.wav"
    return NarrationClip(step_seq=seq, text_sha256=SHA, audio_key=key, duration_ms=duration_ms, words=words)


def manifest(*clips: NarrationClip) -> NarrationManifest:
    return NarrationManifest(voice="v", sample_rate=22050, clips=clips)


def word(w: str, start: int, end: int) -> WordTiming:
    return WordTiming(word=w, start_ms=start, end_ms=end)


# --- value types ---


def test_clip_accepts_ordered_words_inside_the_clip() -> None:
    c = clip(1, 1000, (word("Click", 50, 300), word("Save", 300, 900)))
    assert [w.word for w in c.words] == ["Click", "Save"]


@pytest.mark.parametrize(
    "words",
    [
        (word("late", 900, 1200),),  # ends after the clip
        (word("a", 0, 500), word("b", 400, 600)),  # overlaps the previous word
        (word("back", 500, 400),),  # ends before it starts
    ],
)
def test_clip_rejects_words_that_dont_fit(words: tuple[WordTiming, ...]) -> None:
    with pytest.raises(ValidationError, match="word timings"):
        clip(1, 1000, words)


@pytest.mark.parametrize("bad", ["abc", "G" * 64, "0" * 63])
def test_clip_needs_a_sha256(bad: str) -> None:
    with pytest.raises(ValidationError):
        NarrationClip(step_seq=1, text_sha256=bad, audio_key="narration/v/1.wav", duration_ms=1)


def test_clip_rejects_an_unsafe_audio_key() -> None:
    with pytest.raises(ValidationError):
        NarrationClip(step_seq=1, text_sha256=SHA, audio_key="../etc/passwd", duration_ms=1)


@pytest.mark.parametrize("seqs", [[1, 1], [2, 1]])
def test_manifest_needs_unique_increasing_steps(seqs: list[int]) -> None:
    with pytest.raises(ValidationError, match="unique step_seq"):
        manifest(*(clip(s, 100) for s in seqs))


def test_line_needs_text() -> None:
    with pytest.raises(ValidationError):
        NarrationLine(step_seq=1, text="")


# --- plan_scenes ---


def test_scene_is_the_longer_of_action_and_narration_in_whole_frames() -> None:
    m = manifest(*(clip(i + 1, speech) for i, (_, speech) in enumerate(LABEL_FLOW)))
    actions = {i + 1: action for i, (action, _) in enumerate(LABEL_FLOW)}

    scenes = plan_scenes(m, actions)

    # Same frames as the research table: step 1 is set by the slow navigate, the rest by the voice.
    assert [s.frames for s in scenes] == [179, 53, 128, 144, 190, 138]
    assert [s.start_frame for s in scenes] == [0, 179, 232, 360, 504, 694]


def test_missing_action_counts_as_zero() -> None:
    (scene,) = plan_scenes(manifest(clip(1, 1000)), {})
    assert scene.frames == 51  # 300 + 1000 + 400 = 1700 ms -> 51 frames at 30 fps


def test_ms_values_round_back_to_the_exact_frames_over_a_long_timeline() -> None:
    m = manifest(*(clip(i + 1, 1000 + 37 * i) for i in range(60)))

    scenes = plan_scenes(m, {}, fps=30)

    for s in scenes:
        assert round(s.start_ms / 1000 * 30) == s.start_frame
        assert round((s.start_ms + s.duration_ms) / 1000 * 30) == s.start_frame + s.frames
    # Durations add up to the timeline, with no drift: the compiler sums them as stepDurations.
    end = scenes[-1].start_frame + scenes[-1].frames
    assert sum(s.duration_ms for s in scenes) == round(end * 1000 / 30)


def test_start_frame_leaves_room_for_an_intro_card() -> None:
    scenes = plan_scenes(manifest(clip(1, 1000), clip(2, 1000)), {}, start_frame=60)
    assert [s.start_frame for s in scenes] == [60, 111]
    assert scenes[0].start_ms == 2000


def test_words_move_by_the_lead_in() -> None:
    (scene,) = plan_scenes(manifest(clip(1, 1000, (word("Click", 50, 300),))), {}, lead_in_ms=300)
    assert scene.audio_offset_ms == 300
    assert (scene.words[0].start_ms, scene.words[0].end_ms) == (350, 600)
    assert scene.audio_key == "narration/v/1.wav"


def test_other_fps_and_hold() -> None:
    (scene,) = plan_scenes(manifest(clip(1, 1000)), {}, fps=25, lead_in_ms=0, hold_ms=0)
    assert scene.frames == 25
    assert scene.duration_ms == 1000


@pytest.mark.parametrize(
    ("kwargs", "actions"),
    [({"fps": 0}, {}), ({"hold_ms": -1}, {}), ({"start_frame": -1}, {}), ({}, {1: -5})],
)
def test_plan_scenes_rejects_bad_input(kwargs: dict[str, int], actions: dict[int, int]) -> None:
    with pytest.raises(ValueError):
        plan_scenes(manifest(clip(1, 1000)), actions, **kwargs)


# --- FakeNarrator ---


async def test_fake_narrator_makes_one_valid_clip_per_line() -> None:
    narrator = FakeNarrator(ms_per_char=10)
    lines = [NarrationLine(step_seq=1, text="Click “New label”."), NarrationLine(step_seq=3, text="Wait.")]

    m = await narrator.narrate(lines)

    assert [c.step_seq for c in m.clips] == [1, 3]
    first = m.clips[0]
    assert first.text_sha256 == hashlib.sha256("Click “New label”.".encode()).hexdigest()
    assert first.audio_key == f"narration/fake/{first.text_sha256}.wav"
    assert [w.word for w in first.words] == ["Click", "“New", "label”."]
    assert first.words[-1].end_ms == first.duration_ms
    assert narrator.calls == [lines]


async def test_fake_narrator_is_deterministic() -> None:
    lines = [NarrationLine(step_seq=1, text="Go to the Labels page.")]
    assert await FakeNarrator().narrate(lines) == await FakeNarrator().narrate(lines)


async def test_fake_narrator_can_fail_with_a_reason() -> None:
    with pytest.raises(NarrationError) as err:
        await FakeNarrator(fail="worker_unavailable").narrate([NarrationLine(step_seq=1, text="Hi.")])
    assert err.value.reason == "worker_unavailable"


async def test_fake_narrator_rejects_unordered_steps() -> None:
    lines = [NarrationLine(step_seq=2, text="b"), NarrationLine(step_seq=1, text="a")]
    with pytest.raises(ValueError, match="unique and increasing"):
        await FakeNarrator().narrate(lines)
