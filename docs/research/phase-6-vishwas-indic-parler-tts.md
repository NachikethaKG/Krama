# Indic Parler-TTS: Hindi and Kannada narration on a CPU-only laptop

- **Phase:** 6 (issue #430, decision L8)
- **Researched by:** Vishwas (spike run by Claude Code on Vishwas's laptop, 2026-11-20; decisions by Vishwas)
- **Question(s):** Can `ai4bharat/indic-parler-tts` narrate Hindi and Kannada tutorial steps on a 16 GB CPU-only
  laptop fast enough for video export? What are its license, its training-data licenses, and its speakers? How would
  we get word timings for captions?

## Summary

**Don't adopt (for now).** On CPU it is about **37–39× slower than real time**. Piper is 20–35× *faster* than real
time, so Parler is roughly 1,000× slower. One short step took 78–108 s to synthesise. A 6-step Hindi tutorial would
need about **15 minutes of synthesis**, plus about 1 minute to load the model. It also needs about **5 GB of RAM**
(fp32) and has no word timings. The license is fine: Apache-2.0, and the card lists CC BY 4.0 / CC0 data.

## Setup

- Laptop: Intel i5-14450HX (10 cores / 16 threads), 24 GB RAM, Windows 11. **CPU only**: CPU-only torch wheel,
  `CUDA_VISIBLE_DEVICES=""`, `torch.cuda.is_available() == False` [verified locally].
- The laptop was **busy**, as it normally is during dev work. Docker, Chrome, a backend `pytest` run in another session
  and a game were all running. Free RAM was 0.8–4.8 GB during the runs. The numbers below are for a laptop in normal
  use, not an idle one.
- Scratch venv (not the backend's): Python 3.11, `torch 2.15.0+cpu`, `parler_tts 0.2.2` from
  `git+https://github.com/huggingface/parler-tts.git` at `d108732c`, `transformers 4.46.1`, `protobuf 7.36.2`
  [verified locally].
- Script: `parler_spike.py`. Raw results: `results-t4.json`, `results-default.json`, `results-fetch.json`,
  `results-wavstats.json`, logs `run-*.log`. WAVs for listening are in `wav/`. The model cache and the venv were
  deleted afterwards.

### Install problems found

- **parler-tts pins `transformers==4.46.1`** (`Requires-Dist: transformers<=4.46.1,>=4.46.1`). The repo's last push
  was **2024-12-10** [verified: GitHub API]. It would need its own worker venv, like Piper's
  (`backend/tts-worker`, ADR 0004).
- `sentencepiece` needs a newer `protobuf` than the resolver picked. We had to add `protobuf>=5.28` by hand
  [verified locally: `ImportError: cannot import name 'runtime_version'`].
- `huggingface_hub.snapshot_download` failed on Windows with `WinError 1314` (no symlink privilege without Developer
  Mode). The files were downloaded but not linked. A worker should use `local_dir=` [verified locally].

### The model is gated

- `ai4bharat/indic-parler-tts` is **gated ("auto")**. Every file except `README.md` returns **401** without a
  Hugging Face token [verified: HF API, curl]. No token was set up on this laptop. Shipping it means each user (or
  our installer) needs an HF account and must accept the gate, or we mirror the weights. Apache-2.0 allows mirroring.
- For the spike I used the public mirror `naklitechie/indic-parler-tts@dd37df3c`. Its files are **byte-identical** to
  ai4bharat's at `660bc53c`. The git blob ids of `config.json`, `tokenizer.json` and the LFS pointers of
  `model.safetensors` and `tokenizer.model` match. I recomputed them locally from the downloaded files
  (`results-fetch.json`: all `true`) [verified locally].
- Download size: `model.safetensors` is **3.75 GB**. The description tokenizer comes from `google/flan-t5-large`.

## License, data and speakers

- **Model license: Apache-2.0** (card front matter and "This model is permissively licensed under the Apache 2.0
  license") [verified: model card]. The code (`huggingface/parler-tts`) is also Apache-2.0 [verified: GitHub API].
  Unlike Piper, it has no GPL.
- It is fine-tuned from `ai4bharat/indic-parler-tts-pretrained` [verified: card]. I did not check that card's license.
- **Training data**, as the card's table lists it [verified: model card]:

  | Dataset | Hours | License (as the card states it) |
  |---|---|---|
  | GLOBE | 535 | "CC V1". The HF dataset `MushanW/GLOBE` says **cc0-1.0** [verified: HF API] |
  | IndicTTS | 382 | CC BY 4.0 |
  | LIMMITS | 568 | CC BY 4.0 |
  | Rasa | 288 | CC BY 4.0 (`ai4bharat/Rasa`: cc-by-4.0, gated) [verified: HF API] |

- **Conflict to check:** Piper's Hindi `rohan` card points IndicTTS to IIT Madras's own
  `indictts/downloads/license.pdf`, not to CC BY 4.0 [verified: our phase-6 model-cards]. The IIT-M site did not
  respond from here, so I couldn't read that license [unverified]. If IndicTTS has its own terms, the card's
  "CC BY 4.0" may be wrong.
- In the worst case, CC BY data means we credit the datasets (outro or video description), as for Piper's libritts.
- **A speaker description is needed.** Every call takes a text "caption" that describes the voice. The model uses it
  to pick voice, pace, pitch and recording quality. Without a speaker's name, the voice changes from call to call.
  For a consistent voice, you name a trained speaker in it [verified: card, "Using a specific speaker"]. I used
  `"Rohit speaks at a moderate pace with a clear voice. The recording is of very high quality, … no background noise."`
- Named speakers [verified: card table]:
  - **Hindi:** Rohit, Divya, Aman, Rani. Recommended: **Rohit, Divya**.
  - **Kannada:** Suresh, Anu, Chetan, Vidya. Recommended: **Suresh, Anu**.
- Card quality scores (native-speaker score): Hindi 83.4, Kannada 78.0 [verified: card; not checked by us].
- **Generation samples** (`do_sample: true`), so the same text can sound different on each run unless we fix a seed.
  With seed 430 the default-thread run and the 4-thread run gave the same Hindi clip [verified locally:
  identical length and stats].

## Speed and memory on CPU [verified locally]

The model and its config are fp32. The decoder has 24 layers, hidden size 1024 and 9 codebooks, and outputs 44.1 kHz.

| Measure | Value |
|---|---|
| Import (torch + transformers + parler_tts) | 21.7 s |
| **Model load** (from local disk) | **41.7 s** |
| Warm-up, "नमस्ते।" (not counted) | 59.9 s |
| **Peak working set** (psutil `peak_wset`) | **3.9 GB** |
| Private bytes (committed) while generating | **~5.0 GB** |

| Run | Text | Audio | Synthesis | **RTF** |
|---|---|---|---|---|
| default threads (10), memory-starved | hi1 “New repository” पर क्लिक करें। | 2.95 s | 173.9 s | **59.0** |
| `torch.set_num_threads(4)` | hi1 (same) | 2.95 s | 107.9 s | **36.6** |
| `torch.set_num_threads(4)` | kn1 “New repository” ಕ್ಲಿಕ್ ಮಾಡಿ. | 1.97 s | 77.7 s | **39.4** |

RTF = synthesis time ÷ audio length. Piper ljspeech-medium is 0.029–0.046 on the same laptop
(`phase-5-vishwas-piper-tts.md`).

- **Only 3 of the planned 12 clips ran.** One short clip took 1.3–3 minutes, so the full set (3 hi + 3 kn × 2 thread
  settings) didn't fit in the 45-minute time box. The longer sentences (hi2, hi3, kn2, kn3) were not measured.
- **The default-thread run was paging.** The process had 5.0 GB private but only 3.1 GB in RAM while system free RAM
  was 0.8 GB. I stopped it after one clip. With 4 threads the process used only ~1.5 cores on average. So on this
  busy laptop the limit is memory and per-step overhead, not raw CPU. An idle machine would be faster, but by a few
  times, not by ~1,000× [unverified: no idle run].
- **Projection for a 6-step tutorial** (~6 sentences, ~3–5 s of speech each): about 25 s of audio × RTF ~37 ≈
  **15 minutes per language**, plus ~1 minute to load. The 16 GB laptop would also have about 5 GB less RAM for
  Chrome, Docker and the backend during that time.
- A model of this size might go 2–4× faster with bf16, int8 quantisation or ONNX export
  (`naklitechie/indic-parler-tts-ONNX` exists). Even so it would stay far slower than real time [unverified: not
  tested].

## Audio checks (a human must listen)

The WAVs are `wav/t4-hi1.wav`, `wav/t4-kn1.wav` and `wav/default-hi1.wav` (the same clip as t4-hi1). Measured with
`wav_stats.py` [verified locally]:

- hi1: 2.95 s, 0.63 s of silence at the start, 0.36 s at the end, ~16 characters/s of speech. Looks complete.
- **kn1: 1.97 s with no silence at the start or end.** That is short for "New repository ಕ್ಲಿಕ್ ಮಾಡಿ". It may be
  **cut off**, or start mid-sound. The model stopped on its own EOS token, not on `max_length` (2610) [unverified:
  listen to it].
- I could not judge by ear how the English labels ("New repository") sound, or whether the audio contains anything
  that isn't in the text. Listen to all three files.

## Word timings for captions

- Parler gives **no phoneme or word timings**. It generates audio codec tokens. Krama's `app/tts/align.py` needs
  Piper's per-phoneme sample counts, so it can't be reused.
- Ways to get them:
  - **CTC forced alignment** against the text after TTS (e.g. torchaudio's forced aligner or `ctc-forced-aligner`).
    It needs a Hindi/Kannada acoustic model. The usual multilingual one, **MMS, is CC BY-NC 4.0**
    (`facebook/mms-300m`, `mms-1b-all`, `MahmoudAshraf/mms-300m-1130-forced-aligner`) [verified: HF API], so it is
    not allowed under D1. Allowed options: `ai4bharat/indicwav2vec-hindi` (Apache-2.0, gated) and
    `ai4bharat/indic-conformer-600m-multilingual` (MIT, gated) [verified: HF API licenses]. I did not check whether
    they align well or whether a Kannada wav2vec exists [unverified]. Either adds another 0.3–1 GB model.
  - **Proportional fallback:** trim the silence at the start and end (energy threshold, like `wav_stats.py`), then
    split the speech span over the words by character count (or by aksharas). It is cheap and needs no model. It is
    fine for **captions that highlight one word at a time**: errors are a few hundred ms in a 2–5 s clip. It is weak
    when a quoted English label sits next to Indic words, because they speak at different rates. Use it only as a
    fallback, and mark those captions as estimated [unverified: not measured against ground truth].

## Recommendation

**Don't adopt Indic Parler-TTS for export now** (L8: "adopt only if it fits the laptop"; it doesn't):

1. **Speed:** RTF ~37–39 on CPU, against Piper's ~0.03. A 6-step tutorial would add ~15 minutes per language to an
   export.
2. **Memory:** about 5 GB committed at fp32 (3.9 GB peak working set). On a 16 GB laptop running Chrome, Docker and
   the backend, it pages.
3. **Packaging:** the model is gated (needs a token, or a mirror of 3.75 GB), and the library is stale with a pinned
   `transformers` and a hand-added `protobuf`. It would need its own worker venv.
4. **Word timings:** none. It needs another aligner (the MMS one is NC-licensed) or the proportional fallback.

**Adopt later only if all of these hold:** a quantised or ONNX build reaches RTF ≤ 1 on a 16 GB CPU laptop with
peak RAM ≤ 2 GB; or exports can run on an optional GPU/cloud worker (that breaks rule 10's CPU-only default, so it
must stay opt-in). It also needs a confirmed IndicTTS data license and an allowed aligner. Until then L7 stands:
**Hindi and Kannada get translated captions and VTT only.** Option (c) in the phase-6 note (fine-tune a Piper voice
on IndicVoices-R, CC BY 4.0) is the more promising way to get a fast voice. It is a one-off GPU training job, and
the result would run at Piper speed with Piper's alignment.

## Decisions needed from Vishwas

- **L8:** confirm "don't adopt now". Keep hi/kn as captions-only (L7).
- Should we spend a second short spike on **int8/ONNX Parler** (`naklitechie/indic-parler-tts-ONNX`, licence and
  speed unchecked), or go straight to **fine-tuning Piper on IndicVoices-R** (needs one rented GPU job)?
- If Parler ever ships: accept an **HF-token gate** for users, or mirror the Apache-2.0 weights ourselves?
- Listen to `wav/t4-hi1.wav` and `wav/t4-kn1.wav`. Is the Kannada clip cut off? Are the English labels acceptable?

## Open questions

- What are the real terms of the IIT-M IndicTTS license (`iitm.ac.in/donlab/indictts/downloads/license.pdf`)? The
  site was unreachable from here.
- What license does `ai4bharat/indic-parler-tts-pretrained` (the base model) have?
- What is the speed on an idle 16 GB machine, and on longer sentences (hi2/hi3/kn2/kn3 were not measured)?

## Sources

- https://huggingface.co/ai4bharat/indic-parler-tts (card at `660bc53c`: license, data table, speakers, usage)
- https://huggingface.co/api/models/ai4bharat/indic-parler-tts and `/tree/main` (gated "auto", file blob ids)
- https://huggingface.co/naklitechie/indic-parler-tts (mirror at `dd37df3c`, verified identical)
- https://github.com/huggingface/parler-tts (Apache-2.0, last push 2024-12-10, commit `d108732c`)
- https://huggingface.co/datasets/MushanW/GLOBE (cc0-1.0), https://huggingface.co/datasets/ai4bharat/Rasa (cc-by-4.0)
- https://huggingface.co/facebook/mms-300m, https://huggingface.co/facebook/mms-1b-all (cc-by-nc-4.0)
- https://huggingface.co/ai4bharat/indicwav2vec-hindi (apache-2.0), https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual (mit)
- `docs/research/phase-5-vishwas-piper-tts.md` (Piper speed), `docs/research/phase-6-nachiketha-multiple-languages.md` (L7/L8, voice table)
