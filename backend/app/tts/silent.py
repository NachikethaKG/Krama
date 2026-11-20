"""Captions-only narration (#428, L7): silent clips for languages with no voice we may ship (Hindi, Kannada).

A clip is as long as the text would take to say (about 450 ms per word, 1.5 s at least), and its word timings
are shared out by each word's length. The rest of the export (scene lengths, captions, the .vtt) works exactly
as with a voice, and the video simply has no speech for those steps.
"""

import hashlib
import io
import wave
from collections.abc import Sequence

from app.contracts_gen.tutorial_spec_schema import WordTiming
from app.ports.artifacts import ArtifactStore
from app.ports.narration import NarrationClip, NarrationLine, NarrationManifest

SAMPLE_RATE = 16_000
MS_PER_WORD = 450
MIN_MS = 1_500
VOICE = "silent"


def silent_wav(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    """A mono 16-bit WAV of silence."""
    frames = sample_rate * duration_ms // 1000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def timings(text: str) -> tuple[int, tuple[WordTiming, ...]]:
    """How long the text would take, and each word's share of it by its length (scripts without spaces work
    too: each run of non-space characters is a word)."""
    words = text.split()
    duration = max(MIN_MS, MS_PER_WORD * len(words))
    total = sum(len(w) for w in words) or 1
    out, start = [], 0
    for w in words:
        end = start + duration * len(w) // total
        out.append(WordTiming(word=w, start_ms=start, end_ms=max(start, end)))
        start = end
    return duration, tuple(out)


class SilentNarrator:
    voice = VOICE

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    async def narrate(self, lines: Sequence[NarrationLine]) -> NarrationManifest:
        seqs = [line.step_seq for line in lines]
        if seqs != sorted(set(seqs)):
            raise ValueError(f"step_seq must be unique and increasing, got {seqs}")
        clips = []
        for line in lines:
            duration, words = timings(line.text)
            sha = hashlib.sha256(line.text.encode("utf-8")).hexdigest()
            key = f"narration/{VOICE}/{duration}.wav"  # silence depends only on its length
            if not await self.store.exists(key):
                await self.store.put(key, silent_wav(duration), "audio/wav")
            clips.append(
                NarrationClip(
                    step_seq=line.step_seq, text_sha256=sha, audio_key=key, duration_ms=duration, words=words
                )
            )
        return NarrationManifest(voice=VOICE, sample_rate=SAMPLE_RATE, clips=tuple(clips))
