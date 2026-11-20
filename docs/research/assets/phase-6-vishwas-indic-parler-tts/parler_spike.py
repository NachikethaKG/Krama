"""Issue #430 spike: Indic Parler-TTS on a CPU-only laptop.

Usage (inside the scratch venv, HF_HOME set to the scratch folder):
    python parler_spike.py fetch            # download the mirror + verify it equals ai4bharat's files
    python parler_spike.py bench --threads 0 --tag default
    python parler_spike.py bench --threads 4 --tag t4

Writes results-<tag>.json and wav/<tag>-<lang><n>.wav next to this script.
"""

from __future__ import annotations

import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""  # CPU only, even if a GPU exists
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import argparse
import hashlib
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MIRROR = "naklitechie/indic-parler-tts"
MIRROR_REV = "dd37df3cadd8b7ec06c3ca5cc7c85fc5ea02b399"
# git blob ids of the files in the gated ai4bharat/indic-parler-tts repo at 660bc53c (HF tree API, no auth needed).
# For LFS files the blob is the LFS pointer, which contains the sha256 and size, so a match proves equal bytes.
OFFICIAL_BLOBS = {
    "config.json": "16b7203d25b7827bf0d3cd2eca43f687638866f1",
    "model.safetensors": "74c3556851a9e26d6750263bd141e32b4de04b7e",
    "tokenizer.json": "4e69255622d209ad444a019a340bfbab4a602fb5",
    "tokenizer.model": "2c5c7d3b1e56c6d6fe775e419836cf000f9e42fc",
}
MODEL_DIR = Path(os.environ.get("HF_HOME", HERE / "hf")) / "hub" / "models--naklitechie--indic-parler-tts" / "snapshots" / MIRROR_REV
DESC_TOK_DIR = HERE / "hf" / "flan-t5-large-tokenizer"
LFS_FILES = {"model.safetensors", "tokenizer.model"}

SENTENCES = {
    "hi": [
        "“New repository” पर क्लिक करें।",
        "अपने रिपॉज़िटरी का नाम दर्ज करें, उदाहरण के लिए “notes”।",
        "“Create repository” पर क्लिक करें, फिर पेज के लोड होने तक प्रतीक्षा करें।",
    ],
    "kn": [
        "“New repository” ಕ್ಲಿಕ್ ಮಾಡಿ.",
        "ನಿಮ್ಮ ರೆಪೊಸಿಟರಿಯ ಹೆಸರನ್ನು ನಮೂದಿಸಿ, ಉದಾಹರಣೆಗೆ “notes”.",
        "“Create repository” ಕ್ಲಿಕ್ ಮಾಡಿ, ನಂತರ ಪುಟ ಲೋಡ್ ಆಗುವವರೆಗೆ ಕಾಯಿರಿ.",
    ],
}
# Recommended speakers from the model card: Hindi Rohit/Divya, Kannada Suresh/Anu.
DESCRIPTIONS = {
    "hi": "Rohit speaks at a moderate pace with a clear voice. The recording is of very high quality, "
    "with the speaker's voice sounding clear and very close up, with no background noise.",
    "kn": "Suresh speaks at a moderate pace with a clear voice. The recording is of very high quality, "
    "with the speaker's voice sounding clear and very close up, with no background noise.",
}


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def file_blob_id(path: Path, lfs: bool) -> str:
    if not lfs:
        return git_blob_sha1(path.read_bytes())
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    pointer = f"version https://git-lfs.github.com/spec/v1\noid sha256:{h.hexdigest()}\nsize {path.stat().st_size}\n"
    return git_blob_sha1(pointer.encode())


def fetch() -> None:
    # snapshot_download needs symlinks on Windows (fails without Developer Mode, WinError 1314), so the
    # files were fetched once and missing ones copied from blobs/; verify the snapshot folder directly.
    from huggingface_hub import hf_hub_download

    local = MODEL_DIR
    took = None
    name = json.loads((MODEL_DIR / "config.json").read_text())["text_encoder"]["_name_or_path"]
    for f in ("tokenizer_config.json", "special_tokens_map.json", "spiece.model", "tokenizer.json"):
        hf_hub_download(name, f, local_dir=DESC_TOK_DIR)
    checks = {name: file_blob_id(local / name, name in LFS_FILES) == blob for name, blob in OFFICIAL_BLOBS.items()}
    out = {"mirror": MIRROR, "revision": MIRROR_REV, "matches_official": checks}
    (HERE / "results-fetch.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    if not all(checks.values()):
        sys.exit("mirror does not match the official files")


class PeakRss:
    """Polls RSS every 50 ms. On Windows psutil also reports peak_wset (true peak working set)."""

    def __init__(self) -> None:
        import psutil

        self.proc = psutil.Process()
        self.peak = 0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self.proc.memory_info().rss)
            time.sleep(0.05)

    def report(self) -> dict:
        mi = self.proc.memory_info()
        return {
            "rss_now_mb": round(mi.rss / 2**20),
            "rss_peak_polled_mb": round(max(self.peak, mi.rss) / 2**20),
            "peak_wset_mb": round(getattr(mi, "peak_wset", 0) / 2**20),
        }


def bench(threads: int, tag: str, seed: int, limit: int) -> None:
    mem = PeakRss()
    t_import = time.perf_counter()
    import soundfile as sf
    import torch
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer, set_seed

    import_s = time.perf_counter() - t_import
    if threads:
        torch.set_num_threads(threads)
    device = "cpu"
    local = str(MODEL_DIR)

    t0 = time.perf_counter()
    model = ParlerTTSForConditionalGeneration.from_pretrained(local).to(device)
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(local)
    # The description tokenizer is flan-t5-large's (model.config.text_encoder._name_or_path); fetched with
    # local_dir (no symlinks) by `fetch`.
    desc_tok = AutoTokenizer.from_pretrained(str(DESC_TOK_DIR))
    load_s = time.perf_counter() - t0
    mem_after_load = mem.report()
    sr = model.config.sampling_rate
    print(json.dumps({"load_s": round(load_s, 1), "import_s": round(import_s, 1), "threads": torch.get_num_threads(), **mem_after_load}), flush=True)

    def synth(text: str, description: str):
        d = desc_tok(description, return_tensors="pt").to(device)
        p = tokenizer(text, return_tensors="pt").to(device)
        set_seed(seed)
        t = time.perf_counter()
        with torch.inference_mode():
            gen = model.generate(
                input_ids=d.input_ids,
                attention_mask=d.attention_mask,
                prompt_input_ids=p.input_ids,
                prompt_attention_mask=p.attention_mask,
            )
        took = time.perf_counter() - t
        audio = gen.cpu().numpy().squeeze()
        return audio, took

    # Warm-up (one short English-free phrase), not counted.
    _, warm_s = synth("नमस्ते।", DESCRIPTIONS["hi"])
    print(json.dumps({"warmup_s": round(warm_s, 1), **mem.report()}), flush=True)

    rows = []
    wav_dir = HERE / "wav"
    wav_dir.mkdir(exist_ok=True)
    for lang, texts in SENTENCES.items():
        for i, text in enumerate(texts[:limit], 1):
            audio, took = synth(text, DESCRIPTIONS[lang])
            secs = len(audio) / sr
            name = f"{tag}-{lang}{i}.wav"
            sf.write(wav_dir / name, audio, sr, subtype="PCM_16")
            rows.append(
                {
                    "lang": lang,
                    "n": i,
                    "text": text,
                    "words": len(text.split()),
                    "synth_s": round(took, 2),
                    "audio_s": round(secs, 2),
                    "rtf": round(took / secs, 2) if secs else None,
                    "wav": f"wav/{name}",
                }
            )
            rows[-1].update(mem.report())
            print(json.dumps(rows[-1], ensure_ascii=False), flush=True)

    out = {
        "tag": tag,
        "torch": torch.__version__,
        "torch_threads": torch.get_num_threads(),
        "cuda_available": torch.cuda.is_available(),
        "sampling_rate": sr,
        "seed": seed,
        "import_s": round(import_s, 1),
        "load_s": round(load_s, 1),
        "warmup_s": round(warm_s, 1),
        "mem_after_load": mem_after_load,
        "mem_end": mem.report(),
        "rows": rows,
        "per_lang_rtf": {
            lang: round(
                sum(r["synth_s"] for r in rows if r["lang"] == lang)
                / sum(r["audio_s"] for r in rows if r["lang"] == lang),
                2,
            )
            for lang in SENTENCES
            if any(r["lang"] == lang for r in rows)
        },
    }
    (HERE / f"results-{tag}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    b = sub.add_parser("bench")
    b.add_argument("--threads", type=int, default=0, help="0 = torch default")
    b.add_argument("--tag", default="default")
    b.add_argument("--seed", type=int, default=430)
    b.add_argument("--limit", type=int, default=3, help="sentences per language")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch()
    else:
        bench(a.threads, a.tag, a.seed, a.limit)
