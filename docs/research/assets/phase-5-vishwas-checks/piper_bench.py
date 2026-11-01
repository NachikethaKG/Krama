"""Phase 5 check: Piper speed, memory and word timings on real Krama step texts.

Run from a scratch venv (NOT the backend venv; piper-tts is GPL-3.0-or-later, see the note):

    uv venv -p 3.12 .venv && uv pip install -p .venv "piper-tts[alignment]==1.8.0" psutil
    .venv/Scripts/python -m piper.download_voices --data-dir voices en_US-ljspeech-medium ...
    .venv/Scripts/python -I -X utf8 piper_bench.py --voices voices --texts steps.txt --out results-piper.json
    # weaker-laptop stand-in: --cores 4 --threads 4 (4 logical cores AND 4 onnxruntime threads; see main())

steps.txt = the 104 distinct `workflow_steps.instruction_text` values in the dev database (one per line).
--wav-dir writes every clip as a WAV so you can listen to them.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import statistics
import time
import wave
from pathlib import Path

import psutil
from piper import PiperVoice

# Phoneme symbols that carry no sound of their own: stress marks, length, pauses, sentence markers, punctuation.
_SKIP = set("ˈˌːˑ^$_ ,.;:!?\"'()-—–…“”‘’") | {"ʲ"}


def phoneme_chars(phonemes: list[str]) -> list[str]:
    return [p for p in phonemes if p not in _SKIP]


def word_timings(
    voice: PiperVoice, text: str, stream: list[tuple[str, int, int]], rate: int
) -> tuple[list[dict], float]:
    """Map Piper's per-phoneme sample counts onto the text's whitespace words.

    espeak joins some words ("In the" -> one phoneme word) and expands others ("#d73a4a" -> six), so word
    boundaries can't be counted. Instead: phonemize every text word on its own, line those phoneme letters up with
    the letters actually spoken (difflib), and give each word the span of the spoken letters it matched.
    Returns (timings, fraction of reference phoneme letters that found a match).
    """
    words = text.split()
    ref: list[tuple[str, int]] = []  # (phoneme letter, word index)
    for i, w in enumerate(words):
        for sentence in voice.phonemize(w):
            ref.extend((c, i) for c in phoneme_chars(sentence))
    spoken = [(c, s, e) for c, s, e in stream if c not in _SKIP]
    sm = difflib.SequenceMatcher(None, [c for c, _ in ref], [c for c, _, _ in spoken], autojunk=False)
    span: dict[int, list[int]] = {}
    matched = 0
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            wi = ref[a + k][1]
            _, s, e = spoken[b + k]
            lo_hi = span.setdefault(wi, [s, e])
            lo_hi[0], lo_hi[1] = min(lo_hi[0], s), max(lo_hi[1], e)
            matched += 1
    total = stream[-1][2] if stream else 0
    out: list[dict] = []
    for i, w in enumerate(words):
        if i in span:
            s, e = span[i]
        else:  # no letter matched (e.g. a lone symbol): squeeze it between its neighbours
            prev_end = out[-1]["end_ms"] * rate // 1000 if out else 0
            nxt = next((span[j][0] for j in range(i + 1, len(words)) if j in span), total)
            s, e = prev_end, max(prev_end, nxt)
        out.append(
            {"word": w, "start_ms": s * 1000 // rate, "end_ms": e * 1000 // rate, "matched": i in span}
        )
    # Words must not overlap or go backwards (contract WordTiming has no such rule, but captions need it).
    for a, b in zip(out, out[1:]):
        b["start_ms"] = max(b["start_ms"], a["end_ms"])
        b["end_ms"] = max(b["end_ms"], b["start_ms"])
    return out, (matched / len(ref) if ref else 1.0)


def synth(voice: PiperVoice, text: str) -> tuple[bytes, int, list[tuple[str, int, int]]]:
    audio = bytearray()
    stream: list[tuple[str, int, int]] = []
    pos = 0
    rate = voice.config.sample_rate
    for chunk in voice.synthesize(text, include_alignments=True):
        audio += chunk.audio_int16_bytes
        for a in chunk.phoneme_alignments or []:
            n = int(a.num_samples)
            stream.append((a.phoneme, pos, pos + n))
            pos += n
        pos = len(audio) // 2  # chunks (sentences) follow each other exactly
    return bytes(audio), rate, stream


def bench_voice(model: Path, texts: list[str], wav_dir: Path | None) -> dict:
    proc = psutil.Process()
    rss0 = proc.memory_info().rss
    t0 = time.perf_counter()
    voice = PiperVoice.load(model, include_alignments=True)
    load_s = time.perf_counter() - t0
    synth(voice, "Warm up.")
    clips = []
    peak = proc.memory_info().rss
    for i, text in enumerate(texts):
        t = time.perf_counter()
        audio, rate, stream = synth(voice, text)
        ms = (time.perf_counter() - t) * 1000
        audio_ms = len(audio) // 2 * 1000 / rate
        aligned_samples = stream[-1][2] if stream else 0
        words, match = word_timings(voice, text, stream, rate)
        peak = max(peak, proc.memory_info().rss)
        clips.append(
            {
                "text": text,
                "synth_ms": round(ms, 1),
                "audio_ms": round(audio_ms),
                "alignment_covers_audio": aligned_samples == len(audio) // 2,
                "phoneme_match": round(match, 3),
                "words_unmatched": [w["word"] for w in words if not w["matched"]],
                "words": [{k: w[k] for k in ("word", "start_ms", "end_ms")} for w in words],
            }
        )
        if wav_dir:
            wav_dir.mkdir(parents=True, exist_ok=True)
            with wave.open(str(wav_dir / f"{model.stem}-{i:03d}.wav"), "wb") as f:
                f.setnchannels(1), f.setsampwidth(2), f.setframerate(rate)
                f.writeframes(audio)
    synth_total = sum(c["synth_ms"] for c in clips) / 1000
    audio_total = sum(c["audio_ms"] for c in clips) / 1000
    per = sorted(c["synth_ms"] for c in clips)
    n_words = sum(len(c["words"]) for c in clips)
    unmatched = sum(len(c["words_unmatched"]) for c in clips)
    return {
        "voice": model.stem,
        "model_mb": round(model.stat().st_size / 1e6, 1),
        "sample_rate": voice.config.sample_rate,
        "load_s": round(load_s, 2),
        "rss_mb_after_load": round((proc.memory_info().rss - rss0) / 1e6),
        "rss_mb_peak_process": round(peak / 1e6),
        "clips": len(clips),
        "audio_s": round(audio_total, 1),
        "synth_s": round(synth_total, 1),
        "rtf": round(synth_total / audio_total, 3),
        "synth_ms_p50": per[len(per) // 2],
        "synth_ms_p95": per[int(len(per) * 0.95)],
        "words_per_minute": round(n_words / (audio_total / 60)),
        "alignment_covers_audio_all": all(c["alignment_covers_audio"] for c in clips),
        "phoneme_match_mean": round(statistics.mean(c["phoneme_match"] for c in clips), 3),
        "words_total": n_words,
        "words_unmatched": unmatched,
        "clips_detail": clips,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--voices", type=Path, required=True)
    ap.add_argument("--texts", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only", nargs="*", help="voice names (default: every .onnx in --voices)")
    ap.add_argument("--cores", type=int, help="pin to this many logical cores (weaker-laptop stand-in)")
    ap.add_argument("--threads", type=int, help="onnxruntime intra-op threads (use with --cores)")
    ap.add_argument("--wav-dir", type=Path)
    args = ap.parse_args()
    if args.cores:
        psutil.Process().cpu_affinity(list(range(args.cores)))
    if args.threads:
        # PiperVoice.load builds onnxruntime.SessionOptions() itself. Pinning cores alone is NOT enough: onnxruntime
        # still starts one spinning thread per physical core, and on 4 pinned cores a 9 s run took over 10 minutes.
        import onnxruntime

        real = onnxruntime.SessionOptions

        def options() -> onnxruntime.SessionOptions:
            o = real()
            o.intra_op_num_threads = args.threads
            o.inter_op_num_threads = 1
            return o

        onnxruntime.SessionOptions = options  # type: ignore[misc]
    texts = [t.strip() for t in args.texts.read_text(encoding="utf-8").splitlines() if t.strip()]
    models = sorted(args.voices.glob("*.onnx"))
    if args.only:
        models = [m for m in models if m.stem in args.only]
    results = []
    for m in models:
        r = bench_voice(m, texts, args.wav_dir)
        summary = {k: v for k, v in r.items() if k != "clips_detail"}
        print(json.dumps(summary), flush=True)
        results.append(r)
    meta = {
        "cpu": os.environ.get("PROCESSOR_IDENTIFIER", ""),
        "logical_cores_used": args.cores or psutil.cpu_count(),
        "onnx_threads": args.threads or "default",
        "ram_gb": round(psutil.virtual_memory().total / 1e9),
    }
    args.out.write_text(
        json.dumps({"meta": meta, "voices": results}, indent=1, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
