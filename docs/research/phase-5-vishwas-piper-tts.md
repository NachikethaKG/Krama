# Piper TTS: voices, licenses, CPU speed and word timings

- **Phase:** 5
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-11-01; decisions by Vishwas)
- **Question(s):** **Piper TTS:** voice quality, speed on CPU, and the **license of each voice model** (they differ). Can Piper output word or phoneme timings, so captions match the audio?

## Findings

Checks ran in a scratch venv (not the backend's), on an Intel i5-14450HX (10 cores / 16 threads), 24 GB RAM,
Windows 11, CPU only. Scripts and raw results: [`assets/phase-5-vishwas-checks/`](assets/phase-5-vishwas-checks/).
The text corpus is real: the **104 distinct `workflow_steps.instruction_text` values** in the dev database
(`steps.txt`, average 43 characters, longest 95). They include hard cases like `#d73a4a`, `notes.md`,
`krama-scroll-9d7902`, curly quotes and `…`.

### Which Piper

- `rhasspy/piper` (MIT) is **archived**; its README says "Development has moved: https://github.com/OHF-Voice/piper1-gpl"
  [verified: GitHub API `archived: true`, last push 2025-08-26].
- The maintained project is **`OHF-Voice/piper1-gpl`, license GPL-3.0** [verified: GitHub API]. PyPI package
  `piper-tts` **1.8.0** (2026-09-04), license **GPL-3.0-or-later**, `requires-python >=3.9`, `cp39-abi3` wheels incl.
  **`win_amd64`** (34 MB) [verified: pypi.org/project/piper-tts]. It embeds **espeak-ng** for phonemes
  (GPL-3.0) [verified: piper1-gpl README; espeak-ng GitHub API].
- `uv pip install "piper-tts[alignment]"` on Windows pulled piper-tts 1.8.0, onnxruntime 1.31.1, onnx 1.23.2; no
  compiler, no system espeak, no GPU [verified locally].
- What the GPL means for us: the GPL FAQ says modules "linked together in a shared address space" are "almost surely"
  one program, while "pipes, sockets and command-line arguments are communication mechanisms normally used between
  two separate programs" [verified: gnu.org/licenses/gpl-faq.html#MereAggregation]. Krama has **no license file**
  (GitHub `license: null`). Importing `piper` in the backend would make the backend one program with GPL code.

### Voice licenses (English)

Every voice has a `MODEL_CARD` with its dataset's license, and Piper's docs warn "some voices may have restrictive
licenses" [verified: piper1-gpl `docs/VOICES.md`]. All 38 English cards, fetched at piper-voices commit
`b4e358ff` (2026-10-30), are in `assets/phase-5-vishwas-checks/voice-licenses.txt` [verified].

| Group | Voices | Dataset license | Usable for Krama? |
|---|---|---|---|
| Trained from scratch on public-domain audio | **ljspeech** (medium, high), **kristin** (medium), **norman** (medium), **cori** (en_GB, medium, high) | public domain (LJ Speech, LibriVox) | **Yes** |
| Fine-tuned from a public-domain voice | john (from kristin), bryce | public domain | Yes |
| Trained from scratch, attribution | libritts (high, multi-speaker) | CC BY 4.0 | Yes, with credit |
| **lessac** (low, medium, high) | lessac | **Blizzard 2013 license: "exclusively for Research Purposes", excludes "development, marketing, commercialisation… of voice synthesis"** [verified: cstr.ed.ac.uk lessac license] | **No** |
| Fine-tuned **from lessac** | ~20 voices: amy-medium, alan-medium, alba, aru, arctic, joe, mike, sam, kusal, northern_english_male, vctk, libritts_r, … | their own data is often CC BY / CC0 / Apache, but the starting model is lessac | **Avoid**: they inherit lessac's weights; whether that carries the research-only terms is unclear [unverified] |
| Non-commercial data | ryan (all), hfc_female, hfc_male, semaine, l2arctic | CC BY-NC(-SA) 4.0 | **No** |
| "See URL" | amy-low, danny, kathleen-low, jenny_dioco, alan-low | Mimic 3 / dataset repos | not checked |

The default voice in Piper's own docs (`en_US-lessac-medium`) is one we must **not** ship.

### Speed and memory on CPU [verified locally: `piper_bench.py`, `results-piper.json`, `results-piper-4cores.json`]

All 104 texts, one clip each, after one warm-up:

| Voice | Model | RAM (process) | 16 threads: RTF | p50 / p95 per clip | 4 cores + 4 threads: RTF | p50 / p95 | Speaking rate |
|---|---|---|---|---|---|---|---|
| ljspeech-medium | 64 MB | 452 MB | 0.029 | 80 / 162 ms | 0.046 | 129 / 254 ms | 133 wpm |
| norman-medium | 64 MB | 420 MB | 0.029 | 69 / 143 ms | 0.043 | 108 / 226 ms | 150 wpm |
| kristin-medium | 64 MB | 434 MB | 0.030 | 79 / 143 ms | – | – | 143 wpm |
| lessac-medium (reference only) | 63 MB | 408 MB | 0.029 | 73 / 128 ms | – | – | 152 wpm |
| ljspeech-high | 114 MB | 525 MB | 0.164 | 457 / 966 ms | 0.284 | 786 / 1637 ms | 136 wpm |
| cori-high | 114 MB | 528 MB | 0.161 | 410 / 784 ms | – | – | 149 wpm |

RTF = synthesis time ÷ audio length. Loading a voice takes 2.5–3.1 s; the longest real step is 8.4 s of speech.

- **Medium voices are 20–35× faster than real time, even on 4 cores.** A 6-step tutorial is under 2 s of
  synthesis. TTS will never be the slow part of an export; Remotion rendering will be.
- **Set onnxruntime's thread count explicitly.** `PiperVoice.load` builds `onnxruntime.SessionOptions()` with defaults
  (one intra-op thread per physical core). Pinning the process to 4 cores without lowering the thread count turned a
  9 s run into **more than 10 minutes** (threads waiting on each other) [verified locally]. With other programs busy
  (Chrome, Docker, ~33% CPU), 15 interleaved rounds of one step gave p50 907 ms with default threads vs **146 ms with
  4** and 232 ms with 2 (`piper_threads.py`, `results-threads.txt`). Latency was noisy on every setting (p90 1.6–3.6 s):
  this laptop slows background processes, so the absolute numbers are rough. The ranking held.
- Voice quality is a listening judgement. Vishwas listened to all 7 voices saying the same 4 hard step texts and chose
  **ljspeech-medium**.

### Word and phoneme timings

- **Piper gives phoneme timings, not word timings.** With `PiperVoice.load(..., include_alignments=True)` (needs
  the `onnx` package, `piper-tts[alignment]`) each `AudioChunk` has `phoneme_alignments`: per phoneme, the number of
  audio samples [verified: piper1-gpl `docs/ALIGNMENTS.md`]. The doc calls it "experimental". The CLI and the HTTP
  server don't expose it; only the Python (and C++) API does [verified: `python -m piper --help`, `docs/API_HTTP.md`].
- The sample counts add up **exactly** to the audio length for all 104 texts × 7 voices [verified locally:
  `alignment_covers_audio_all: true`]. Chunks are sentences, back to back.
- **Words can't be counted off the phonemes.** espeak joins and splits words: `In the` → `ɪnðə` (one phoneme word),
  `#d73a4a` → `hˈaʃ dˈiː sˈɛvənti θɹˈiːʲ ˈeɪ fˈɔːɹ ˈeɪ` (six) [verified locally].
- What works: phonemize **each text word on its own** (`voice.phonemize(word)`), drop stress marks, pauses and
  punctuation, line those letters up with the spoken phoneme letters (`difflib.SequenceMatcher`), and give each text
  word the time span of the spoken letters it matched. On the corpus: **97.6 % of phoneme letters match; 8 of 707
  words unmatched, all of them the word "a"** (alone it is the letter name `ˈeɪ`, in a sentence `ɐ`). Those get squeezed
  in between their neighbours [verified locally].
- **Checked against the audio itself, not the aligner** (`check_word_timings.py`, ljspeech-medium / norman-medium):
  words found are loud (median −18 dBFS, 0–2 of ~580 words quieter than −40 dB), and the pauses the aligner found
  between words (≥ 120 ms, e.g. at commas) are near-silent (median −30 / −52 dBFS). Shifting every timing by ±250 ms
  makes 12–124 words fall into silence and the gaps loud (−19 dBFS) [verified locally]. So the timings are well inside
  ±250 ms; a tighter bound wasn't measured.
- Example (ljspeech-medium): `In the “New label” dialog, enter “#d73a4a” in “Color”.` → `dialog,` 917–1474 ms,
  comma pause, `enter` 2031–2229, `“#d73a4a”` 2275–4806 (the colour takes 2.5 s to say), clip 5515 ms.
- These map directly onto the contract: `Caption.words: WordTiming[] {word, start_ms, end_ms}` "when known at compile
  time (Piper, Phase 5)" [verified: `contracts/schemas/tutorial-spec.schema.json`].

## Recommendation

Decided by Vishwas on 2026-11-01 (see `phase-5-decisions-alignment.md`):

1. **Voice: `en_US-ljspeech-medium`** (public domain, trained from scratch, 64 MB). Never ship lessac or a voice
   fine-tuned from it, or an NC voice. Record the voice name and its MODEL_CARD license in the ADR and next to the
   model file. Fixed voice for Phase 5; no voice picker.
2. **Run Piper as a separate worker process**, not as a backend import. A small worker with its own venv
   (`piper-tts[alignment]==1.8.0`) reads JSON lines on stdin (`{text, out_path}`) and writes the WAV plus the phoneme
   alignments as JSON. `tts/` (backend) does the word alignment, caching and storage. This keeps GPL code out of
   `backend/pyproject.toml`. Exact layout (where the worker's `pyproject` lives, how the export job starts it) is part of
   #120. **NEEDS ADR** ("Piper voice choice and license" is already planned in Sprint 5.1).
3. Set `intra_op_num_threads` (default 2, setting `TTS_THREADS`) and `inter_op_num_threads=1` in the worker, because
   it shares the CPU with Chromium and Remotion.
4. **Word timings = phoneme alignments + per-word diff**, as in `piper_bench.py`. Store them per clip; they fill
   `Caption.words` and the `.vtt` sidecar.

## Open questions

- Alignments are labelled "experimental" upstream. Pin `piper-tts==1.8.0` and keep a test that fails if
  `phoneme_alignments` disappears or stops summing to the audio length.
- Whether a voice fine-tuned from lessac inherits the Blizzard terms is a legal question [unverified]; we avoid it.
- The worker's own license: as a separate program that imports `piper`, it should be GPL-3.0 itself (a header +
  `COPYING` in its folder). Krama as a whole still has no license; choosing one is outside Phase 5.
- Not measured on Nachiketha's laptop. The 4-core run is a stand-in; check `piper_bench.py --cores 4 --threads 2` there.

## Links
- https://github.com/OHF-Voice/piper1-gpl (README, `docs/ALIGNMENTS.md`, `docs/API_PYTHON.md`, `docs/API_HTTP.md`, `docs/VOICES.md`)
- https://github.com/rhasspy/piper (archived)
- https://pypi.org/project/piper-tts/
- https://huggingface.co/rhasspy/piper-voices (MODEL_CARD per voice)
- https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html
- https://www.gnu.org/licenses/gpl-faq.html#MereAggregation
