"""Run Krama's own Piper worker on non-English voices and align words with backend/app/tts/align.py.

Run with the BACKEND venv python (for app.tts.align); the worker runs in the tts-worker venv.
Usage: python tts_lang_check.py <voices_dir> <out_dir>
"""

import json
import subprocess
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, r"C:\Krama\backend")
from app.tts.align import align_words  # noqa: E402

WORKER_PY = r"C:\Krama\backend\tts-worker\.venv\Scripts\python.exe"
WORKER = r"C:\Krama\backend\tts-worker\worker.py"

TEXTS = {
    "de_DE-thorsten-medium": [
        "Klicken Sie auf „New repository“.",
        "Geben Sie im Feld „Repository name *“ einen Namen ein, zum Beispiel „my-app“.",
        "Klicken Sie auf „Create repository“.",
    ],
    "mr_IN-google-medium": [
        "“New repository” वर क्लिक करा.",
        "“Repository name *” मध्ये नाव लिहा, उदाहरणार्थ “my-app”.",
        "नवीन रिपॉझिटरी तयार करण्यासाठी बटणावर क्लिक करा.",
    ],
    "te_IN-padmavathi-medium": [
        "“New repository” పై క్లిక్ చేయండి.",
        "“Repository name *” లో పేరు నమోదు చేయండి, ఉదాహరణకు “my-app”.",
        "కొత్త రిపోజిటరీ సృష్టించడానికి బటన్ నొక్కండి.",
    ],
}


def main() -> None:
    vdir, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    for voice, texts in TEXTS.items():
        t0 = time.perf_counter()
        p = subprocess.Popen(
            [WORKER_PY, WORKER, "--model", str(vdir / f"{voice}.onnx"), "--threads", "2"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", env={"PYTHONIOENCODING": "utf-8", "SYSTEMROOT": r"C:\Windows"},
        )
        ready = json.loads(p.stdout.readline())
        load_s = time.perf_counter() - t0
        rows = []
        for i, text in enumerate(texts):
            wav = out / f"{voice}-{i}.wav"
            t1 = time.perf_counter()
            p.stdin.write(json.dumps({"id": str(i), "text": text, "wav_path": str(wav)}, ensure_ascii=False) + "\n")
            p.stdin.flush()
            ans = json.loads(p.stdout.readline())
            synth_ms = int((time.perf_counter() - t1) * 1000)
            if not ans.get("ok"):
                rows.append({"text": text, "error": ans.get("error")})
                continue
            al = align_words(text, ans["phonemes"], ans["word_phonemes"], ans["sample_rate"])
            dur = ans["samples"] * 1000 // ans["sample_rate"]
            spoken = "".join(ph for ph, _ in ans["phonemes"])
            rows.append({
                "text": text,
                "duration_ms": dur,
                "synth_ms": synth_ms,
                "sum_ok": sum(n for _, n in ans["phonemes"]) == ans["samples"],
                "phoneme_match": round(al.phoneme_match, 3),
                "words": [(w.word, w.start_ms, w.end_ms) for w in al.words],
                "spoken_phonemes": spoken,
                "word_phonemes": ["".join(w) for w in ans["word_phonemes"]],
            })
        p.stdin.close()
        p.wait(timeout=30)
        report[voice] = {"ready": ready, "load_s": round(load_s, 2), "rows": rows}
    (out / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for v, r in report.items():
        print("==", v, r["ready"], "load", r["load_s"], "s")
        for row in r["rows"]:
            if "error" in row:
                print("  ERROR", row["error"])
                continue
            print(f"  {row['duration_ms']} ms (synth {row['synth_ms']} ms) sum_ok={row['sum_ok']} match={row['phoneme_match']}")
            print("   ", row["words"])
            print("    spoken:", row["spoken_phonemes"][:160])


if __name__ == "__main__":
    main()
