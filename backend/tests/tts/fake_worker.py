"""A stand-in for backend/tts-worker/worker.py that speaks the same JSON-lines protocol, without Piper.

Run as `python fake_worker.py <mode> [voice]`. Modes: ok, bad_start, not_ready, crash, error, hang, garbled,
wrong_id, bad_sum, no_wav. In `ok` mode a text from fixtures/worker-answers.json gets its recorded answer; any
other text gets 80 ms per letter, one phoneme per letter.
"""

import json
import struct
import sys
import time
import wave
from pathlib import Path
from typing import Any

RATE = 22050
_RECORDED = Path(__file__).parent / "fixtures" / "worker-answers.json"
FIXTURES = {a["text"]: a for a in json.loads(_RECORDED.read_text("utf-8"))["answers"]}


def answer_for(text: str) -> dict[str, Any]:
    if text in FIXTURES:
        a = FIXTURES[text]
        return {k: a[k] for k in ("sample_rate", "samples", "phonemes", "word_phonemes")}
    per_letter = RATE * 80 // 1000
    phonemes = [[c.lower(), per_letter] for c in text if not c.isspace()]
    words = [[c.lower() for c in w] for w in text.split()]
    return {
        "sample_rate": RATE,
        "samples": per_letter * len(phonemes),
        "phonemes": phonemes,
        "word_phonemes": words,
    }


def write_wav(path: str, samples: int) -> None:
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(struct.pack(f"<{samples}h", *([0] * samples)))


def send(message: object) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    mode = sys.argv[1]
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if mode == "bad_start":
        print("not json", flush=True)
        return
    if mode == "not_ready":
        send({"ready": False, "error": "FileNotFoundError: voice.onnx"})
        sys.exit(2)
    send(
        {
            "ready": True,
            "voice": sys.argv[2] if len(sys.argv) > 2 else "en_US-ljspeech-medium",
            "sample_rate": RATE,
        }
    )
    for line in sys.stdin:
        request = json.loads(line)
        if mode == "crash":
            print("Traceback: boom", file=sys.stderr, flush=True)
            sys.exit(1)
        if mode == "hang":
            time.sleep(30)
        if mode == "garbled":
            print("{oops", flush=True)
            continue
        if mode == "wrong_id":
            send({"id": "999", "ok": True})
            continue
        if mode == "error":
            send({"id": request["id"], "ok": False, "error": "RuntimeError: espeak failed"})
            continue
        a = answer_for(request["text"])
        if mode != "no_wav":
            write_wav(request["wav_path"], int(a["samples"]))
        if mode == "bad_sum":
            a["samples"] = int(a["samples"]) + 1
        send({"id": request["id"], "ok": True, **a})


if __name__ == "__main__":
    main()
