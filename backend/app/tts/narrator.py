"""`PiperNarrator`: the `Narrator` port, with Piper running in the separate worker (docs/adr/0004).

Every step's clip is stored once per (voice, text): `narration/<voice>/<sha256(text)>.wav` plus a `.json`
next to it with the duration and word timings. A new export, or a new version whose step texts didn't change,
reuses them without starting the worker at all.
"""

import hashlib
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from app.ports.artifacts import ArtifactStore
from app.ports.models import ArtifactNotFoundError
from app.ports.narration import (
    NarrationClip,
    NarrationError,
    NarrationLine,
    NarrationManifest,
    WordTiming,
)
from app.tts.align import align_words
from app.tts.process import PiperProcess

_WAV = b"RIFF"


class ClipMeta(BaseModel):
    """The `.json` stored next to each clip."""

    model_config = ConfigDict(extra="forbid")

    voice: str
    sample_rate: int
    samples: int
    duration_ms: int
    phoneme_match: float
    words: list[WordTiming]


class PiperNarrator:
    def __init__(
        self,
        store: ArtifactStore,
        *,
        voice: str,
        start_worker: Callable[[], PiperProcess],
    ) -> None:
        self.store = store
        self.voice = voice
        self._start_worker = start_worker

    async def narrate(self, lines: Sequence[NarrationLine]) -> NarrationManifest:
        seqs = [line.step_seq for line in lines]
        if seqs != sorted(set(seqs)):
            raise ValueError(f"step_seq must be unique and increasing, got {seqs}")

        metas: dict[int, ClipMeta] = {}
        todo: list[NarrationLine] = []
        for line in lines:
            meta = await self._cached(line.text)
            if meta is None:
                todo.append(line)
            else:
                metas[line.step_seq] = meta

        if todo:
            async with self._start_worker() as worker:
                if worker.voice and worker.voice != self.voice:
                    raise NarrationError(
                        "voice_missing", f"worker loaded {worker.voice!r}, expected {self.voice!r}"
                    )
                with tempfile.TemporaryDirectory(prefix="krama-tts-") as tmp:
                    for line in todo:
                        metas[line.step_seq] = await self._synthesize(worker, line.text, Path(tmp))

        sample_rate = next(iter(metas.values())).sample_rate if metas else 22050
        clips = tuple(
            NarrationClip(
                step_seq=line.step_seq,
                text_sha256=_sha(line.text),
                audio_key=self._key(line.text, "wav"),
                duration_ms=metas[line.step_seq].duration_ms,
                words=tuple(metas[line.step_seq].words),
            )
            for line in lines
        )
        return NarrationManifest(voice=self.voice, sample_rate=sample_rate, clips=clips)

    async def _cached(self, text: str) -> ClipMeta | None:
        wav_key, meta_key = self._key(text, "wav"), self._key(text, "json")
        if not (await self.store.exists(wav_key) and await self.store.exists(meta_key)):
            return None
        try:
            meta = ClipMeta.model_validate_json((await self.store.get(meta_key)).data)
        except (ArtifactNotFoundError, ValidationError):
            return None  # deleted in between, or an older format: make it again
        return meta if meta.voice == self.voice else None

    async def _synthesize(self, worker: PiperProcess, text: str, tmp: Path) -> ClipMeta:
        wav_path = tmp / f"{_sha(text)}.wav"
        result = await worker.synthesize(text, wav_path)
        try:
            data = wav_path.read_bytes()
        except OSError as e:
            raise NarrationError("synthesis_failed", f"the TTS worker wrote no audio: {e}") from e
        if not data.startswith(_WAV) or result.sample_rate <= 0:
            raise NarrationError("synthesis_failed", "the TTS worker wrote something that isn't a WAV file")
        if sum(n for _, n in result.phonemes) != result.samples:
            # Piper's alignments are "experimental": catch an upgrade that changes what they mean.
            raise NarrationError("synthesis_failed", "phoneme timings don't add up to the clip length")
        try:
            alignment = align_words(text, result.phonemes, result.word_phonemes, result.sample_rate)
        except ValueError as e:
            raise NarrationError("synthesis_failed", f"can't align words: {e}") from e
        meta = ClipMeta(
            voice=self.voice,
            sample_rate=result.sample_rate,
            samples=result.samples,
            duration_ms=result.samples * 1000 // result.sample_rate,
            phoneme_match=round(alignment.phoneme_match, 3),
            words=list(alignment.words),
        )
        # The .json goes last: a clip counts as cached only once both files are there.
        await self.store.put(self._key(text, "wav"), data, "audio/wav")
        await self.store.put(
            self._key(text, "json"), meta.model_dump_json().encode("utf-8"), "application/json"
        )
        return meta

    def _key(self, text: str, ext: str) -> str:
        return f"narration/{self.voice}/{_sha(text)}.{ext}"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
