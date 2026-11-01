# 0004 — Narration voice: Piper `en_US-ljspeech-medium`, run as a separate GPL worker

- **Status:** accepted
- **Deciders:** Vishwas (research and decision, 2026-11-01), Nachiketha (review)
- **Issue:** #121 · Research: [`phase-5-vishwas-piper-tts.md`](../research/phase-5-vishwas-piper-tts.md) (#117),
  decisions D1–D2 in [`phase-5-decisions-alignment.md`](../research/phase-5-decisions-alignment.md)

## Context
Phase 5 exports tutorials as MP4 with narration made on the CPU by Piper. Two license questions had to be settled
before #120 adds any code.

**1. Piper itself is GPL.** The MIT-licensed `rhasspy/piper` is archived and points to `OHF-Voice/piper1-gpl`. Its
PyPI package `piper-tts` (1.8.0, 2026-09-04, Windows wheels) is **GPL-3.0-or-later** and embeds espeak-ng
(GPL-3.0). Krama has no license yet. The GPL FAQ treats modules linked in one address space as one program, and
programs that talk through pipes or command-line arguments as normally separate (#MereAggregation).

**2. Voice licenses differ per voice.** Each voice's `MODEL_CARD` names its training data. The 38 English cards were
checked (piper-voices commit `b4e358ff`, list in `docs/research/assets/phase-5-vishwas-checks/voice-licenses.txt`):

| Voices | Training data license | Allowed |
|---|---|---|
| **ljspeech** (medium, high), kristin, norman, cori (en_GB): trained from scratch | public domain (LJ Speech, LibriVox) | yes |
| john, bryce (fine-tuned from a public-domain voice) | public domain | yes |
| libritts (high) | CC BY 4.0 | yes, with credit |
| **lessac** (Piper's default voice) | Blizzard 2013 license: research purposes only, excludes developing or commercialising voice synthesis | **no** |
| ~20 voices fine-tuned from lessac (amy-medium, alba, joe, mike, sam, vctk, libritts_r, …) | own data is CC BY / CC0 / Apache, but the starting weights are lessac | **no** (unclear inheritance) |
| ryan, hfc_female, hfc_male, semaine, l2arctic | CC BY-NC(-SA) 4.0 | **no** |

Measured on Vishwas's laptop with the 104 real step texts in the dev DB: medium voices run 20–35× faster than real
time on the CPU (64 MB model, ~450 MB RAM). High voices are 5× slower for no clear gain in a screen tutorial.
Vishwas listened to 7 candidates on the same hard step texts.

## Decision
1. **The narration voice is `en_US-ljspeech-medium`**: LJ Speech dataset, public domain, trained from scratch (its
   `MODEL_CARD`). One fixed voice in Phase 5; exports record which voice they used.
2. **Never ship lessac, a voice fine-tuned from lessac, or a non-commercial (NC) voice.** A new voice needs its
   `MODEL_CARD` checked (dataset license and base model) and a line in this ADR's table.
3. **Piper runs as a separate program, never as a backend dependency.** `backend/tts-worker/` has its own
   `pyproject.toml` (`piper-tts[alignment]==1.8.0`), its own lock file, a GPL-3.0-or-later notice, and a small
   `worker.py` that reads JSON lines on stdin and writes WAV files plus phoneme alignments. `app/tts/` starts it as a
   subprocess and does everything else (word timings, caching, storage) in plain Python. `piper-tts` never appears in
   `backend/pyproject.toml` or `backend/uv.lock`.
4. The worker sets onnxruntime's intra-op threads explicitly (`TTS_THREADS`, default 2). The default (one thread per
   core) stalled when the CPU was busy with other programs.

## Alternatives considered
- **Import `piper` in the backend.** Simplest and a little faster (no process start-up), but it puts GPL code in the
  backend's address space, so the backend becomes a GPL program and any future license for Krama has to be
  GPL-compatible. Rejected: the worker costs ~100 lines and keeps that choice open.
- **The archived MIT `rhasspy/piper` binary.** Unmaintained, still bundles GPL espeak-ng, and has no alignment API.
  Rejected.
- **Piper's HTTP server in a Docker sidecar.** Same isolation, but it returns only WAV (no alignments), and another
  container costs memory on 16 GB laptops. Rejected.
- **`en_US-lessac-medium`** (Piper's documented default): research-only data. Rejected.
- **norman / kristin / cori-high:** also public domain; ljspeech-medium was preferred by ear, and cori-high is 5×
  slower. Each is a drop-in replacement under this ADR.
- **Web Speech API** (the player's voice): browser-only, can't render offline into a file. Stays in the player.

## Consequences
- Easier: the backend's dependency tree stays free of GPL code. The voice is reproducible: pinned package, pinned model
  file, recorded in each export.
- Harder: one more environment to set up (`just backend tts-setup` creates the worker venv and downloads the 64 MB
  model), and CI can't run real Piper. Backend tests use a fake worker that speaks the same JSON protocol, and one
  opt-in test runs the real worker.
- Piper's alignments are labelled "experimental" upstream. The pin to 1.8.0 plus a test that checks the alignment sum
  catches a breaking upgrade.
- If Krama picks a license later, this ADR needs no change. The worker folder stays GPL whatever Krama chooses.
