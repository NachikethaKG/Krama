# Phase 5 Decisions & Alignment: narration, presets, export API and storage

- **Phase:** 5 (Video export)
- **Document type:** Decision record + research summary (for Nachiketha to read; for both agents to build on)
- **Decided by:** Vishwas, 2026-11-01. Nachiketha was fully busy, so Vishwas also took the "Together" decisions (#119)
  and the ones that touch Nachiketha's work (`packages/video-exporter`, `export/`, the export dialog); they are marked
  **[N]** below. Nachiketha: if you disagree with one, raise it on the issue it applies to before that issue's coding
  starts.
- **Written by:** Claude Code on Vishwas's laptop.
- **References:**
  - `phase-5-vishwas-piper-tts.md`, `phase-5-vishwas-audio-pipeline.md`, `phase-5-vishwas-video-storage.md` (#117)
  - checks and raw results: `assets/phase-5-vishwas-checks/`
  - `docs/phases/phase-5-video-export.md`

Not covered here: Nachiketha's own research (#118: Remotion license, render time on CPU, rrweb inside Remotion vs
screenshots, FFmpeg chapters and captions). It's still open. Several decisions below assume Remotion can do things
#118 should confirm; those are listed in §4.

---

## 1. Research in five minutes

**Piper.** The maintained Piper is `piper-tts` 1.8.0 (OHF-Voice/piper1-gpl), **GPL-3.0-or-later**, with Windows
wheels; the old MIT repo is archived. Voice licenses differ a lot. `lessac`, Piper's default voice, is trained on
data licensed for research only, and about 20 other English voices are fine-tuned from it. **ljspeech**, kristin,
norman and cori are trained from scratch on public-domain audio. Medium voices run **20–35× faster than real time**
on a laptop CPU (a 6-step tutorial is under 2 s), as long as onnxruntime's thread count is set; the default can stall
when other programs are busy.

**Timings.** Piper gives per-phoneme sample counts (exact to the sample), not words. Lining up each word's own
phonemes with the spoken ones gives word timings for 99 % of words (only "a" misses). Checked against the audio
energy: words are loud, pauses are silent, and a ±250 ms shift breaks both.

**Step length.** The compiler's word-count estimate is shorter than the real Piper speech in **54–75 % of real step
texts**, by up to 4.3 s. The player hides that by holding until speech ends; a video can't. Recorded actions take
0.2–0.5 s (except navigation), so narration sets the pace.

**Joining audio.** Placing clips at scene starts (in Python or FFmpeg) is accurate to under 5 ms over 60 scenes, but
only if scene starts are counted **in whole frames**. Rounding milliseconds and frames separately drifts 85 ms by step
6 and 1 s by step 60.

**Size.** ~**5 MB per minute** at 1080p H.264 CRF 18 (Remotion's default); a 6-step tutorial is ~2.4 MB. One run's
rrweb recording is 9.3 MB, so videos are small. **MinIO's open-source repo is archived**, so "S3/MinIO later" needs a
new target.

---

## 2. Decisions

| # | Decision | Applies to | Owner |
|---|---|---|---|
| D1 | **Voice `en_US-ljspeech-medium`** (public domain, from scratch). Never ship lessac, lessac-derived or NC voices. One fixed voice; no voice field in the export request yet (the server records the voice used). | #120, #121 | Vishwas |
| D2 | **Piper runs as a separate worker process** with its own venv (`piper-tts[alignment]==1.8.0`), talking JSON over stdin/stdout: text in, WAV + phoneme alignments out. No `piper-tts` in `backend/pyproject.toml`. onnxruntime threads set explicitly (`TTS_THREADS`, default 2). | #120, #121 | Vishwas |
| D3 | **[N] Narration = one WAV per step + a manifest**, no premixed track. Manifest per workflow version: `{voice, sample_rate, steps: [{step_seq, text_sha256, audio_key, duration_ms, words: WordTiming[]}]}`. Clips cached by `(voice, sha256(text))`. Remotion places each clip in its scene's `<Sequence>`. | #120, #122, #126 | both |
| D4 | **[N] Scene length = `max(recorded action ms, 300 ms lead-in + clip + 400 ms hold)`, rounded up to whole frames at 30 fps**, fed to the compiler through its existing `stepDurations` / `wordTimings` options. Every ms → position (scene, caption cue, chapter) uses the same frame-snapped starts. | #120, #122 | both |
| D5 | **Narration is generated inside the export job**, through a `Narrator` port implemented by `tts/`; not when a workflow is saved. | #120, #126 | both |
| D6 | **[N] Two presets:** `landscape` 1920×1080 (16:9) and `portrait` 1080×1920 (9:16). Both 30 fps, H.264 CRF 18, AAC, `+faststart`. No 720p option. | #122, #124, #127 | both |
| D7 | **[N] 16:9 framing of 1280×800 (16:10) recordings: fit + side bars.** The whole viewport (1728×1080) is centred on a plain background when the camera isn't zoomed; nothing is cropped. | #122 | Nachiketha |
| D8 | **[N] 9:16 follows the highlight:** each scene crops a 9:16 window around the highlight bbox (zoom ≥ 1.6× so text is readable), panning with the scene's camera easing; steps without a highlight show a fitted overview; captions in the bottom third. (A centre crop of a real GitHub page cut off the labels.) | #122 | Nachiketha |
| D9 | **[N] Intro 2 s + outro 2 s.** Intro: tutorial title + site. Outro: "Verified on <site>, <date of the version's run>" + "Made with Krama". | #122 | Nachiketha |
| D10 | **[N] Cursor, click ripple and highlight as in the spec; camera zoom ON in 16:9** (the TutorialSpec `camera`, scale ≤ 3, 450 ms pan), although the player's zoom defaults to off: a video can't be paused to squint. | #122 | Nachiketha |
| D11 | **[N] Captions burned in + a WebVTT sidecar**, both from the Piper word timings. | #122, #124, #126 | both |
| D12 | **[N] Chapters:** `Intro`, `Step N: <scene title or caption>` per step, `Done`. A 6-step tutorial has 8 chapters. | #122, #126 | Nachiketha |
| D13 | **Export statuses:** `queued → rendering → ready \| failed`, and `ready → expired` when cleanup deletes the file (the row stays). | #124, #125, #126 | both (contract) |
| D14 | **[N] Seam:** `POST /workflows/{id}/exports` writes an `exports` row (`queued`) and calls an **`ExportQueue` port** that enqueues the arq job. The job reports through an **`ExportStore` port** (Vishwas implements): `rendering` + progress %, then `ready` (artifact key, size, duration, vtt key) or `failed` (error code). The UI **polls** `GET /exports/{id}` every 2 s; no SSE. A mock `ExportQueue` finishes with a fixture MP4, so #124 and #127 work before #126 exists. | #124, #126, #127 | both (contract) |
| D15 | **Only a `verified` workflow can be exported** (its current version). `outdated` or a pending heal → `409 workflow_not_verified`. | #124 | Vishwas |
| D16 | **Re-export reuses work:** the same (workflow version, preset, voice) that is `queued`, `rendering` or `ready` is returned with `200`; a `failed` or `expired` one is rendered again (`202`). | #124 | Vishwas |
| D17 | **Owner only.** Create, status and download need the workflow's owner (`404` otherwise, like `GET /workflows/{id}`). No MP4 download on share links in Phase 5. | #124 | Vishwas |
| D18 | **Retention:** keep the newest `ready` export per (workflow version, preset); delete others after **30 days**; delete oldest-first above **`EXPORTS_MAX_GB`** (default 5); a failed export's partial file is deleted right away. arq cron job. | #125 | Vishwas |
| D19 | **Local disk for Phase 5; SeaweedFS (Apache-2.0) later**, when the renderer runs on another machine or we deploy. MinIO OSS is archived. Needs an ADR (architecture.md says "S3/MinIO"). | #125 | Vishwas |
| D20 | **Download is a `FileResponse`** (HTTP Range: 200/206/416, verified on Starlette 1.7) with `Content-Disposition: attachment`. `ArtifactStore` gains `video/mp4`, `audio/wav`, `text/vtt`, a store-this-file call, a local path/URL for serving, `delete`, and list/size of a prefix (contract-change PR). | #124, #125 | both (contract) |

### The presets (from D6–D12)

| | `landscape` | `portrait` |
|---|---|---|
| Size | 1920×1080, 30 fps | 1080×1920, 30 fps |
| Codec | H.264 CRF 18, AAC, `+faststart` | same |
| Framing | whole 16:10 viewport with side bars; camera zoom from the spec | 9:16 window that follows the highlight, zoom ≥ 1.6× |
| Cursor / ripple / highlight | on, as in the spec | on, as in the spec |
| Captions | burned in + `.vtt` | burned in (bottom third) + `.vtt` |
| Intro / outro | 2 s / 2 s | 2 s / 2 s |
| Chapters | Intro, Step 1..N, Done | same |
| Voice | ljspeech-medium | same |
| Expected size (6 steps, ~32 s with cards) | ~2.8 MB | ~2 MB |

---

## 3. What this means for each issue

- **#120 Piper narration (Vishwas):** the worker (D2), the `Narrator` port + `tts/` implementation (word alignment
  from `assets/phase-5-vishwas-checks/piper_bench.py`, clip cache, manifest D3, scene length D4). Tests use a fake
  narrator plus a few `results-piper.json` clips as fixtures; the real-voice test is opt-in (needs the 64 MB model).
  The port is a contract change (`ports/`), so that goes first.
- **#121 ADR (Vishwas):** voice choice and license table (D1), GPL and the separate worker (D2).
- **#122 Remotion composition (Nachiketha):** D3, D4, D6–D12. Reads the manifest's clips per scene; uses the
  frame-snapped scene starts everywhere.
- **#123 Spike (Nachiketha):** unaffected, but D8 (follow-the-highlight 9:16) needs page-coordinate bboxes in
  whichever approach wins.
- **#124 Export API (Vishwas):** contract-change PR first: `Export` model (status D13, preset D6, progress, sizes,
  error), `exports` table, `ExportQueue` / `ExportStore` ports (D14), artifact content types (D20). Then the routes
  with D15–D17 against the mock queue.
- **#125 Storage and cleanup (Vishwas):** D18–D20; the narration clip cache needs its own rule (clips no manifest has
  referenced for 30 days).
- **#126 Export job (Nachiketha):** implements `ExportQueue` (arq), calls the `Narrator` port, then the renderer,
  reports through `ExportStore`, stores the MP4 + `.vtt` through `ArtifactStore`.
- **#127 Export dialog (Nachiketha):** two presets only (D6), no voice picker (D1), polls status every 2 s (D14),
  "expired, export again" (D13), owner only (D17).

---

## 4. Still open

- **#118 (Nachiketha's research) isn't done.** These decisions assume, unverified: Remotion can place audio per
  `<Sequence>` and mix it, can burn captions and write a `.vtt`, can write FFmpeg chapter metadata, and renders a 1080p
  minute on a 16 GB CPU-only laptop in acceptable time. If #118 says otherwise, revisit D3, D11, D12 or D6.
- **Remotion license** (#118) decides whether Remotion stays at all.
- The 300 ms lead-in and 400 ms hold (D4) are guesses tuned to the player; check them on the first real export.
- Piper alignments are marked "experimental" upstream; pin 1.8.0 and keep a test that fails if they change.
- Choosing a license for Krama itself is outside Phase 5. D2 keeps that choice open.
