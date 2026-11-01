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

SETUP_HINT = "run `just backend tts-setup`"


def worker_command(settings: Settings) -> list[str]:
    """`uv run` the worker in its own project, so its venv (and Piper) stays separate from the backend's."""
    model = settings.tts_voices_dir / f"{settings.tts_voice}.onnx"
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


def get_narrator() -> Narrator:
    """The narrator for this process. The worker only starts when a clip isn't cached yet."""
    settings = get_settings()
    return PiperNarrator(
        get_artifact_store(),
        voice=settings.tts_voice,
        start_worker=lambda: PiperProcess(worker_command(settings)),
    )


__all__ = ["PiperNarrator", "PiperProcess", "get_narrator", "worker_command"]
