# Krama TTS worker: Piper narration for the video export.
# Copyright (C) 2026 the Krama authors
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
# Public License as published by the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version. See COPYING. It is a separate program from the Krama backend (docs/adr/0004).
"""Read JSON requests on stdin, one per line; write one JSON answer per line on stdout.

    python worker.py --model voices/en_US-ljspeech-medium.onnx --threads 2

Start-up: {"ready": true, "voice": "<model stem>", "sample_rate": 22050}
          {"ready": false, "error": "..."}  (then it exits)
Request:  {"id": "1", "text": "Click Save.", "wav_path": "C:/tmp/1.wav"}
Answer:   {"id": "1", "ok": true, "sample_rate": 22050, "samples": 26112,
           "phonemes": [["^", 1536], ["k", 1024], ...],   # every phoneme (IPA) with its sample count
           "word_phonemes": [["k", "l", ...], ...]}       # each whitespace word phonemized on its own
          {"id": "1", "ok": false, "error": "..."}

stdout carries only these JSON lines (UTF-8); anything else goes to stderr.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import wave
from pathlib import Path
from typing import Any


def _limit_threads(threads: int) -> None:
    """PiperVoice.load builds onnxruntime.SessionOptions() itself; the default (one thread per core) stalls
    when the CPU is busy (docs/research/phase-5-vishwas-piper-tts.md), so wrap it to set the thread count."""
    ort: Any = importlib.import_module("onnxruntime")
    real = ort.SessionOptions

    def options() -> Any:
        o = real()
        o.intra_op_num_threads = threads
        o.inter_op_num_threads = 1
        return o

    ort.SessionOptions = options


def _send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _synthesize(voice: Any, text: str, wav_path: str) -> dict[str, Any]:
    rate = int(voice.config.sample_rate)
    audio = bytearray()
    phonemes: list[list[Any]] = []
    for chunk in voice.synthesize(text, include_alignments=True):
        audio += chunk.audio_int16_bytes
        alignments = chunk.phoneme_alignments
        if alignments is None:
            raise RuntimeError("the voice gave no phoneme alignments (is the onnx package installed?)")
        phonemes.extend([a.phoneme, int(a.num_samples)] for a in alignments)
    with wave.open(wav_path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(bytes(audio))
    word_phonemes = [[p for sentence in voice.phonemize(w) for p in sentence] for w in text.split()]
    samples = len(audio) // 2
    return {"sample_rate": rate, "samples": samples, "phonemes": phonemes, "word_phonemes": word_phonemes}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()
    sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    try:
        _limit_threads(args.threads)
        piper: Any = importlib.import_module("piper")
        voice = piper.PiperVoice.load(args.model, include_alignments=True)
    except Exception as e:  # any start-up failure is reported the same way
        _send({"ready": False, "error": f"{type(e).__name__}: {e}"})
        return 2
    _send({"ready": True, "voice": args.model.stem, "sample_rate": int(voice.config.sample_rate)})
    for line in sys.stdin:
        if not line.strip():
            continue
        request_id = None
        try:
            request = json.loads(line)
            request_id = request["id"]
            _send({"id": request_id, "ok": True, **_synthesize(voice, request["text"], request["wav_path"])})
        except Exception as e:  # one bad request must not kill the worker
            _send({"id": request_id, "ok": False, "error": f"{type(e).__name__}: {e}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
