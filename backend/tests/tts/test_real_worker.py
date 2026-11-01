"""The real Piper worker, end to end. Runs only after `just backend tts-setup` (CI has no model and skips)."""

import pytest

from app.config import get_settings
from app.ports import NarrationLine, plan_scenes
from app.ports.fakes import FakeArtifactStore
from app.tts import PiperNarrator, worker_command
from app.tts.process import PiperProcess

settings = get_settings()
MODEL = settings.tts_voices_dir / f"{settings.tts_voice}.onnx"
WORKER_VENV = settings.tts_worker_dir / ".venv"

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        not (MODEL.is_file() and WORKER_VENV.is_dir()),
        reason="Piper not set up: run `just backend tts-setup`",
    ),
]


async def test_real_piper_narrates_a_tutorial() -> None:
    store = FakeArtifactStore()
    narrator = PiperNarrator(
        store, voice=settings.tts_voice, start_worker=lambda: PiperProcess(worker_command(settings))
    )
    lines = [
        NarrationLine(step_seq=1, text='Go to the "Labels" page.'),
        NarrationLine(step_seq=2, text="In the “New label” dialog, enter “#d73a4a” in “Color”."),
    ]

    manifest = await narrator.narrate(lines)

    assert manifest.voice == "en_US-ljspeech-medium" and manifest.sample_rate == 22050
    for clip, line in zip(manifest.clips, lines, strict=True):
        assert 500 < clip.duration_ms < 10_000
        assert [w.word for w in clip.words] == line.text.split()
        assert store.artifacts[clip.audio_key].data.startswith(b"RIFF")
    scenes = plan_scenes(manifest, {1: 5956, 2: 287})
    assert scenes[0].frames == 179  # the slow navigate sets step 1
    assert scenes[1].duration_ms > manifest.clips[1].duration_ms  # the voice sets step 2
