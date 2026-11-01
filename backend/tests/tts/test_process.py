"""The worker client against a fake worker process that speaks the same protocol (no Piper needed)."""

import sys
from pathlib import Path

import pytest

from app.ports.narration import NarrationError
from app.tts.process import PiperProcess
from tests.tts.conftest import fake_process

pytestmark = pytest.mark.anyio


async def test_start_reads_the_voice_then_synthesizes(tmp_path: Path) -> None:
    async with fake_process("ok") as worker:
        assert (worker.voice, worker.sample_rate) == ("en_US-ljspeech-medium", 22050)
        first = await worker.synthesize("Click Save.", tmp_path / "1.wav")
        second = await worker.synthesize("Wait for the page to update.", tmp_path / "2.wav")

    assert first.samples == sum(n for _, n in first.phonemes)
    assert len(first.word_phonemes) == 2
    assert (tmp_path / "1.wav").read_bytes().startswith(b"RIFF")
    assert len(second.word_phonemes) == 6  # recorded real answer from the fixtures


async def test_unicode_text_round_trips(tmp_path: Path) -> None:
    async with fake_process("ok") as worker:
        result = await worker.synthesize("Enter “notes.md” in “Name your file…”.", tmp_path / "u.wav")
    assert result.word_phonemes[1][0] == "“"


@pytest.mark.parametrize(
    ("mode", "message"),
    [("bad_start", "bad start line"), ("not_ready", "couldn't load the voice")],
)
async def test_start_failures(mode: str, message: str) -> None:
    with pytest.raises(NarrationError, match=message) as err:
        async with fake_process(mode):
            pass
    assert err.value.reason == "worker_unavailable"


async def test_a_missing_program_is_worker_unavailable() -> None:
    with pytest.raises(NarrationError) as err:
        async with PiperProcess([str(Path(sys.executable).with_name("no-such-program.exe"))]):
            pass
    assert err.value.reason == "worker_unavailable"


@pytest.mark.parametrize(
    ("mode", "reason", "message"),
    [
        ("crash", "worker_unavailable", "Traceback: boom"),
        ("error", "synthesis_failed", "espeak failed"),
        ("garbled", "synthesis_failed", "bad JSON"),
        ("wrong_id", "synthesis_failed", "wrong request"),
    ],
)
async def test_request_failures(tmp_path: Path, mode: str, reason: str, message: str) -> None:
    async with fake_process(mode) as worker:
        with pytest.raises(NarrationError, match=message) as err:
            await worker.synthesize("Click Save.", tmp_path / "x.wav")
    assert err.value.reason == reason


async def test_a_hung_worker_times_out_and_is_killed(tmp_path: Path) -> None:
    worker = fake_process("hang", request_timeout_s=0.5)
    async with worker:
        with pytest.raises(NarrationError, match=r"longer than 0\.5 s") as err:
            await worker.synthesize("Click Save.", tmp_path / "x.wav")
        proc = worker._proc
    assert err.value.reason == "synthesis_failed"
    assert proc is not None and proc.returncode is not None  # closed, not left running


async def test_synthesize_after_close_fails(tmp_path: Path) -> None:
    worker = fake_process("ok")
    async with worker:
        pass
    with pytest.raises(NarrationError, match="isn't running"):
        await worker.synthesize("Click Save.", tmp_path / "x.wav")
