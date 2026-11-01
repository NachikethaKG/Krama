"""Talks to the Piper worker (backend/tts-worker/worker.py) over stdin/stdout, one JSON object per line.

The worker is a separate GPL program (docs/adr/0004); this module only starts it and exchanges JSON with it.
"""

import asyncio
import contextlib
import json
import os
from collections import deque
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError

from app.ports.narration import NarrationError, NarrationErrorReason


class Synthesis(BaseModel):
    """One answer from the worker: the WAV is at the requested path."""

    model_config = ConfigDict(extra="ignore")

    sample_rate: int
    samples: int
    phonemes: list[tuple[str, int]]
    word_phonemes: list[list[str]]


class _Ready(BaseModel):
    ready: bool
    voice: str = ""
    sample_rate: int = 0
    error: str = ""


class PiperProcess:
    """One running worker. Use as `async with PiperProcess(cmd) as p: await p.synthesize(text, path)`.

    Requests are sent one at a time. Any failure to start, a crash, a hang or a garbled answer raises
    NarrationError, never a bare OSError or JSON error.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        start_timeout_s: float = 120.0,
        request_timeout_s: float = 60.0,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = list(command)
        self.start_timeout_s = start_timeout_s
        self.request_timeout_s = request_timeout_s
        self.env = env
        self.voice = ""
        self.sample_rate = 0
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr: deque[str] = deque(maxlen=20)
        self._stderr_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._next_id = 0

    async def __aenter__(self) -> Self:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", **(self.env or {})}
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=2**22,  # one answer holds every phoneme of a step: allow 4 MB lines
            )
        except OSError as e:
            raise NarrationError("worker_unavailable", f"can't start the TTS worker: {e}") from e
        assert self._proc.stderr is not None
        self._stderr_task = asyncio.create_task(self._drain_stderr(self._proc.stderr))
        try:
            line = await self._read_line(self.start_timeout_s, "start")
            ready = _Ready.model_validate_json(line)
        except ValidationError as e:
            await self.aclose()
            raise NarrationError("worker_unavailable", f"TTS worker sent a bad start line: {e}") from e
        except NarrationError:
            await self.aclose()
            raise
        if not ready.ready:
            await self.aclose()
            raise NarrationError("worker_unavailable", f"TTS worker couldn't load the voice: {ready.error}")
        self.voice, self.sample_rate = ready.voice, ready.sample_rate
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.aclose()

    async def synthesize(self, text: str, wav_path: Path) -> Synthesis:
        if self._proc is None or self._proc.stdin is None:
            raise NarrationError("worker_unavailable", "the TTS worker isn't running")
        async with self._lock:
            self._next_id += 1
            request_id = str(self._next_id)
            # ensure_ascii: the request is plain ASCII whatever the pipe's encoding is.
            payload = json.dumps({"id": request_id, "text": text, "wav_path": str(wav_path)}) + "\n"
            try:
                self._proc.stdin.write(payload.encode("ascii"))
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as e:
                raise NarrationError(
                    "worker_unavailable", f"the TTS worker stopped: {self._stderr_tail()}"
                ) from e
            line = await self._read_line(self.request_timeout_s, "synthesis")
        try:
            answer = json.loads(line)
        except json.JSONDecodeError as e:
            raise NarrationError("synthesis_failed", f"TTS worker sent bad JSON: {line[:200]!r}") from e
        if not isinstance(answer, dict) or answer.get("id") != request_id:
            raise NarrationError("synthesis_failed", f"TTS worker answered the wrong request: {line[:200]!r}")
        if not answer.get("ok"):
            raise NarrationError(
                "synthesis_failed", f"TTS worker failed: {answer.get('error', 'unknown error')}"
            )
        try:
            return Synthesis.model_validate(answer)
        except ValidationError as e:
            raise NarrationError("synthesis_failed", f"TTS worker answer has the wrong shape: {e}") from e

    async def aclose(self) -> None:
        proc, self._proc = self._proc, None
        if proc is not None:
            if proc.stdin is not None and not proc.stdin.is_closing():
                proc.stdin.close()  # EOF: the worker's read loop ends and it exits by itself
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                await proc.wait()
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task
            self._stderr_task = None

    async def _read_line(self, timeout_s: float, what: str) -> str:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=timeout_s)
        except TimeoutError as e:
            reason: NarrationErrorReason = "worker_unavailable" if what == "start" else "synthesis_failed"
            raise NarrationError(reason, f"TTS worker {what} took longer than {timeout_s:g} s") from e
        except ValueError as e:  # line longer than the stream limit
            raise NarrationError("synthesis_failed", f"TTS worker answer too long: {e}") from e
        if not raw:
            await asyncio.sleep(0.05)  # let stderr catch up, so the message says why it died
            raise NarrationError("worker_unavailable", f"the TTS worker stopped: {self._stderr_tail()}")
        return raw.decode("utf-8")

    async def _drain_stderr(self, stream: asyncio.StreamReader) -> None:
        while line := await stream.readline():
            self._stderr.append(line.decode("utf-8", errors="replace").rstrip())

    def _stderr_tail(self) -> str:
        return " | ".join(self._stderr) or "no error output"
