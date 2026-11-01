import json
from collections.abc import Callable
from pathlib import Path

import pytest

from app.config import Settings
from app.ports import NarrationLine, Narrator
from app.ports.fakes import FakeArtifactStore
from app.ports.narration import NarrationError
from app.tts import PiperNarrator, worker_command
from app.tts.process import PiperProcess
from tests.tts.conftest import fake_process

pytestmark = pytest.mark.anyio

VOICE = "en_US-ljspeech-medium"
LINES = [
    NarrationLine(step_seq=1, text="Wait for the page to update."),
    NarrationLine(step_seq=3, text="In the “New label” dialog, enter “#d73a4a” in “Color”."),
]


class Starter:
    """Counts how often the narrator starts a worker."""

    def __init__(self, mode: str = "ok", *args: str) -> None:
        self.mode, self.args, self.starts = mode, args, 0

    def __call__(self) -> PiperProcess:
        self.starts += 1
        return fake_process(self.mode, *self.args)


def narrator(store: FakeArtifactStore, start: Callable[[], PiperProcess]) -> PiperNarrator:
    return PiperNarrator(store, voice=VOICE, start_worker=start)


async def test_one_stored_clip_per_line() -> None:
    store, start = FakeArtifactStore(), Starter()

    manifest = await narrator(store, start).narrate(LINES)

    assert (manifest.voice, manifest.sample_rate) == (VOICE, 22050)
    assert [c.step_seq for c in manifest.clips] == [1, 3]
    for clip in manifest.clips:
        assert clip.audio_key == f"narration/{VOICE}/{clip.text_sha256}.wav"
        wav = store.artifacts[clip.audio_key]
        assert wav.ref.content_type == "audio/wav"
        assert wav.data.startswith(b"RIFF")
        meta = json.loads(store.artifacts[clip.audio_key.replace(".wav", ".json")].data)
        assert meta["duration_ms"] == clip.duration_ms
        assert meta["phoneme_match"] > 0.9
    colour = manifest.clips[1]
    assert len(colour.words) == 9 and colour.duration_ms > 5000  # recorded real Piper answer
    assert start.starts == 1  # one worker for the whole tutorial


async def test_cached_clips_dont_start_the_worker() -> None:
    store = FakeArtifactStore()
    first = await narrator(store, Starter()).narrate(LINES)

    again = Starter("crash")  # would fail if it were started
    second = await narrator(store, again).narrate(LINES)

    assert second == first
    assert again.starts == 0


async def test_only_changed_steps_are_voiced() -> None:
    store = FakeArtifactStore()
    await narrator(store, Starter()).narrate(LINES[:1])
    start = Starter()

    manifest = await narrator(store, start).narrate(
        [*LINES[:1], NarrationLine(step_seq=2, text="Click Save.")]
    )

    assert start.starts == 1
    assert len(manifest.clips) == 2


async def test_a_clip_from_another_voice_is_not_reused() -> None:
    store = FakeArtifactStore()
    await PiperNarrator(store, voice="other", start_worker=Starter("ok", "other")).narrate(LINES[:1])
    # Same text, but the .json says another voice: the cache is keyed by voice, so nothing is shared.
    start = Starter()
    await narrator(store, start).narrate(LINES[:1])
    assert start.starts == 1


@pytest.mark.parametrize(
    ("starter", "reason", "message"),
    [
        (Starter("ok", "en_US-lessac-medium"), "voice_missing", "expected 'en_US-ljspeech-medium'"),
        (Starter("bad_sum"), "synthesis_failed", "don't add up"),
        (Starter("no_wav"), "synthesis_failed", "wrote no audio"),
        (Starter("crash"), "worker_unavailable", "stopped"),
    ],
)
async def test_failures_raise_narration_errors_and_store_nothing(
    starter: Starter, reason: str, message: str
) -> None:
    store = FakeArtifactStore()
    with pytest.raises(NarrationError, match=message) as err:
        await narrator(store, starter).narrate(LINES)
    assert err.value.reason == reason
    assert store.artifacts == {}


async def test_steps_must_be_unique_and_in_order() -> None:
    with pytest.raises(ValueError, match="unique and increasing"):
        await narrator(FakeArtifactStore(), Starter()).narrate(list(reversed(LINES)))


async def test_no_lines_no_worker() -> None:
    start = Starter()
    manifest = await narrator(FakeArtifactStore(), start).narrate([])
    assert manifest.clips == () and start.starts == 0


def test_worker_command_needs_the_voice_model(tmp_path: Path) -> None:
    settings = Settings(tts_voices_dir=tmp_path)
    with pytest.raises(NarrationError, match="tts-setup") as err:
        worker_command(settings)
    assert err.value.reason == "voice_missing"


def test_worker_command_runs_the_worker_project_with_the_thread_limit(tmp_path: Path) -> None:
    (tmp_path / f"{VOICE}.onnx").write_bytes(b"x")
    (tmp_path / f"{VOICE}.onnx.json").write_text("{}")
    cmd = worker_command(Settings(tts_voices_dir=tmp_path, tts_threads=3))
    assert cmd[1:5] == ["run", "--project", str(Settings().tts_worker_dir), "--frozen"]
    assert cmd[-4:] == ["--model", str(tmp_path / f"{VOICE}.onnx"), "--threads", "3"]


def test_piper_narrator_matches_the_port() -> None:
    _: Narrator = PiperNarrator(FakeArtifactStore(), voice=VOICE, start_worker=Starter())
