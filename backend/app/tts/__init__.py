"""Piper narration for the video export (Phase 5, #120), behind the `Narrator` port (app/ports/narration.py).

Piper itself runs in backend/tts-worker (GPL, its own venv; docs/adr/0004). Set it up with
`just backend tts-setup`.
"""

import shutil
from pathlib import Path

from app.config import Settings, get_settings
from app.ports import Narrator
from app.ports.narration import NarrationError
from app.storage import get_artifact_store
from app.tts.narrator import PiperNarrator
from app.tts.process import PiperProcess
from app.tts.silent import SilentNarrator

SETUP_HINT = "run `just backend tts-setup`"


VOICES = {
    "de": "de_DE-thorsten-medium",  # CC0, trained from scratch
    "es": "es_ES-davefx-medium",  # CC0
    "fr": "fr_FR-siwis-medium",  # CC BY 4.0: credited in the outro
}
"""Narration voices per tutorial language (#428, L7; licenses in
docs/research/phase-6-nachiketha-multiple-languages.md). English uses `TTS_VOICE`. Hindi and Kannada have no
voice we may ship yet: captions only (`SILENT`)."""
SILENT = "silent"


def voice_for(language: str, settings: Settings) -> str:
    """The voice an export in `language` is narrated with, or SILENT."""
    if language == "en":
        return settings.tts_voice
    return VOICES.get(language, SILENT)


def worker_command(settings: Settings, voice: str | None = None) -> list[str]:
    """`uv run` the worker in its own project, so its venv (and Piper) stays separate from the backend's."""
    model = settings.tts_voices_dir / f"{voice or settings.tts_voice}.onnx"
    if not model.is_file() or not model.with_suffix(".onnx.json").is_file():
        raise NarrationError("voice_missing", f"voice model {model} not found: {SETUP_HINT}")
    uv = shutil.which("uv")
    if uv is None:
        raise NarrationError("worker_unavailable", "uv isn't on PATH, so the TTS worker can't start")
    worker: Path = settings.tts_worker_dir
    return [
        uv, "run", "--project", str(worker), "--frozen", "--quiet",
        "python", str(worker / "worker.py"), "--model", str(model), "--threads", str(settings.tts_threads),
    ]  # fmt: skip


def get_narrator(language: str = "en") -> Narrator:
    """The narrator for an export in `language` (#428). The worker only starts when a clip isn't cached yet.
    Hindi and Kannada get silent clips sized like speech: captions only (L7)."""
    settings = get_settings()
    voice = voice_for(language, settings)
    if voice == SILENT:
        return SilentNarrator(get_artifact_store())
    return PiperNarrator(
        get_artifact_store(),
        voice=voice,
        start_worker=lambda: PiperProcess(worker_command(settings, voice)),
    )


__all__ = [
    "SILENT",
    "VOICES",
    "PiperNarrator",
    "PiperProcess",
    "SilentNarrator",
    "get_narrator",
    "voice_for",
    "worker_command",
]
