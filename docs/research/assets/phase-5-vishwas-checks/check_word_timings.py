"""Phase 5 check: do the word timings from piper_bench.py line up with the audio itself?

Independent of the aligner: real word spans should be loud, and the pauses the aligner found between words
(>= 120 ms, e.g. at commas) should be near-silent. Shifting every timing by +-250 ms should make both worse.

    python -X utf8 check_word_timings.py results-piper.json <wav-dir> en_US-ljspeech-medium
"""

import json
import math
import struct
import sys
import wave
from pathlib import Path


def rms_db(samples: list[int]) -> float:
    if not samples:
        return -120.0
    r = math.sqrt(sum(s * s for s in samples) / len(samples))
    return 20 * math.log10(max(r, 1) / 32768)


def score(clips: list[dict], wav_dir: Path, voice: str, shift_ms: int) -> dict:
    in_word, in_gap = [], []
    for i, c in enumerate(clips):
        with wave.open(str(wav_dir / f"{voice}-{i:03d}.wav")) as f:
            rate = f.getframerate()
            pcm = struct.unpack(f"<{f.getnframes()}h", f.readframes(f.getnframes()))
        n = len(pcm)

        def cut(a_ms: int, b_ms: int) -> list[int]:
            a = min(max(0, (a_ms + shift_ms) * rate // 1000), n)
            b = min(max(0, (b_ms + shift_ms) * rate // 1000), n)
            return list(pcm[a:b])

        words = c["words"]
        for w in words:
            if w["end_ms"] - w["start_ms"] >= 80:
                in_word.append(rms_db(cut(w["start_ms"], w["end_ms"])))
        for a, b in zip(words, words[1:]):
            if b["start_ms"] - a["end_ms"] >= 120:
                # middle of the gap, so phoneme edges don't count
                in_gap.append(rms_db(cut(a["end_ms"] + 30, b["start_ms"] - 30)))
    med = lambda xs: sorted(xs)[len(xs) // 2] if xs else None  # noqa: E731
    return {
        "shift_ms": shift_ms,
        "words": len(in_word),
        "word_median_db": round(med(in_word), 1),
        "words_quieter_than_-40db": sum(x < -40 for x in in_word),
        "gaps": len(in_gap),
        "gap_median_db": round(med(in_gap), 1) if in_gap else None,
        "gaps_quieter_than_-40db": sum(x < -40 for x in in_gap),
    }


def main() -> None:
    results, wav_dir, voice = json.load(open(sys.argv[1], encoding="utf-8")), Path(sys.argv[2]), sys.argv[3]
    clips = next(v for v in results["voices"] if v["voice"] == voice)["clips_detail"]
    for shift in (0, -250, 250):
        print(json.dumps(score(clips, wav_dir, voice, shift)))


if __name__ == "__main__":
    main()
