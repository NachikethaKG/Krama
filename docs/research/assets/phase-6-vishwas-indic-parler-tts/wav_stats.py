"""Leading/trailing silence and speaking rate of the spike WAVs (helps judge truncation or rambling)."""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
out = {}
for res in sorted(HERE.glob("results-*.json")):
    if res.name == "results-fetch.json" or res.name == "results-wavstats.json":
        continue
    data = json.loads(res.read_text(encoding="utf-8"))
    for row in data["rows"]:
        audio, sr = sf.read(HERE / row["wav"])
        frame = sr // 100  # 10 ms
        n = len(audio) // frame
        rms = np.sqrt((audio[: n * frame].reshape(n, frame) ** 2).mean(axis=1))
        voiced = np.where(rms > max(rms.max() * 0.05, 1e-4))[0]
        lead = voiced[0] * 0.01 if len(voiced) else None
        trail = (n - 1 - voiced[-1]) * 0.01 if len(voiced) else None
        speech = (voiced[-1] - voiced[0] + 1) * 0.01 if len(voiced) else 0
        out[row["wav"]] = {
            "audio_s": row["audio_s"],
            "lead_silence_s": round(lead, 2) if lead is not None else None,
            "trail_silence_s": round(trail, 2) if trail is not None else None,
            "speech_s": round(speech, 2),
            "chars_per_s": round(len(row["text"]) / speech, 1) if speech else None,
            "peak": round(float(np.abs(audio).max()), 3),
        }
(HERE / "results-wavstats.json").write_text(json.dumps(out, indent=2))
json.dump(out, sys.stdout, indent=1)
