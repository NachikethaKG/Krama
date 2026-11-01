# tts-worker: Piper narration (GPL-3.0-or-later)

A separate program, not part of the backend package. [ADR 0004](../../docs/adr/0004-piper-voice-and-license.md)
explains why: `piper-tts` is GPL-3.0-or-later, so it lives in its own venv and the backend only talks to it
through stdin/stdout. **Never add `piper-tts` to `backend/pyproject.toml`.** This folder is licensed under the GPL
(`COPYING`), whatever license the rest of Krama gets.

```powershell
just backend tts-setup        # uv sync this project + download en_US-ljspeech-medium into data/tts/voices
```

The backend starts it (`app/tts/__init__.py: worker_command`) as:

```
uv run --project backend/tts-worker --frozen python backend/tts-worker/worker.py --model <voice>.onnx --threads 2
```

The protocol (JSON lines, UTF-8) is in the docstring of [`worker.py`](worker.py); `backend/tests/tts/fake_worker.py`
speaks the same protocol for tests.

| Setting | Default | |
|---|---|---|
| `TTS_VOICE` | `en_US-ljspeech-medium` | Only voices allowed by ADR 0004 (public-domain data, not lessac-based, not NC) |
| `TTS_VOICES_DIR` | `data/tts/voices` | `<voice>.onnx` + `<voice>.onnx.json` |
| `TTS_THREADS` | `2` | onnxruntime threads. The default (one per core) stalls while the CPU is busy |

Upgrading `piper-tts`: alignments are "experimental" upstream. After `uv lock --upgrade-package piper-tts`, run
`just backend test tests/tts` (the real-worker test checks that phoneme timings still add up to the audio).
