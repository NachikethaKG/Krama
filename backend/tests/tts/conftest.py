import json
import sys
from pathlib import Path
from typing import Any

import pytest

from app.tts.process import PiperProcess

HERE = Path(__file__).parent
FAKE_WORKER = HERE / "fake_worker.py"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def worker_answers() -> list[dict[str, Any]]:
    """Real answers of the Piper worker (en_US-ljspeech-medium, piper-tts 1.8.0) for three real step texts."""
    data = json.loads((HERE / "fixtures" / "worker-answers.json").read_text(encoding="utf-8"))
    answers: list[dict[str, Any]] = data["answers"]
    return answers


def fake_process(mode: str = "ok", *args: str, **kwargs: Any) -> PiperProcess:
    return PiperProcess([sys.executable, str(FAKE_WORKER), mode, *args], **kwargs)
