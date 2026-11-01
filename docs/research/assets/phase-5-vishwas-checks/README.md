# Phase 5 checks (Vishwas, #117)

Run on Vishwas's laptop on 2026-11-01 (i5-14450HX, 24 GB, Windows 11, CPU only). Notes that use them:
`phase-5-vishwas-piper-tts.md`, `phase-5-vishwas-audio-pipeline.md`, `phase-5-vishwas-video-storage.md`.

Use a **scratch venv, not the backend's**: `piper-tts` is GPL-3.0-or-later and must not land in `backend/pyproject.toml`.

```powershell
uv venv -p 3.12 .venv
uv pip install -p .venv "piper-tts[alignment]==1.8.0" imageio-ffmpeg psutil
.venv/Scripts/python -m piper.download_voices --data-dir voices en_US-ljspeech-medium en_US-norman-medium
.venv/Scripts/python -I -X utf8 piper_bench.py --voices voices --texts steps.txt --out results-piper.json --wav-dir wav
.venv/Scripts/python -I -X utf8 piper_bench.py --voices voices --texts steps.txt --out results-piper-4cores.json --cores 4 --threads 4
python -X utf8 check_word_timings.py results-piper.json wav en_US-ljspeech-medium
.venv/Scripts/python -I -X utf8 piper_threads.py voices/en_US-ljspeech-medium.onnx 15
.venv/Scripts/python -I -X utf8 audio_pipeline.py --voice voices/en_US-ljspeech-medium.onnx --work pipe
.venv/Scripts/python -I mp4_size.py --shots <data/artifacts/runs/<run>/steps> --audio pipe/track-a-1.m4a --work mp4
```

| File | What |
|---|---|
| `steps.txt` | the 104 distinct `workflow_steps.instruction_text` values in the dev DB (test corpus) |
| `voice-licenses.txt` | license + base model lines from all 38 English `MODEL_CARD`s (piper-voices `b4e358ff`) |
| `piper_bench.py` → `results-piper*.json` | speed, memory, word timings per voice (per clip in `clips_detail`) |
| `check_word_timings.py` | word spans vs audio energy, with ±250 ms shifts as the control |
| `piper_threads.py` → `results-threads.txt` | latency vs onnxruntime thread count under background load |
| `audio_pipeline.py` → `results-pipeline.json` | scene lengths, two ways to join clips, frame-snapping drift |
| `results-estimate-vs-piper.json` | compiler word-count estimate vs real Piper length, per voice |
| `mp4_size.py` → `results-mp4.json` | MB per minute and x264 encode time per preset/CRF |

Use `-X utf8` on Windows: phoneme symbols crash the cp1252 console (`-I` ignores `PYTHONIOENCODING`).
