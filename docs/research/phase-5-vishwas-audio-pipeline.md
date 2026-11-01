# Audio pipeline: one clip per step, joined to the video's timeline

- **Phase:** 5
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-11-01; decisions by Vishwas)
- **Question(s):** **Audio pipeline:** generate one clip per step, then join them with FFmpeg. How do you make step timing follow narration length?

## Findings

Script and raw results: [`assets/phase-5-vishwas-checks/audio_pipeline.py`](assets/phase-5-vishwas-checks/audio_pipeline.py),
`results-pipeline.json`, `results-estimate-vs-piper.json`. FFmpeg 7.1 came from the `imageio-ffmpeg` 0.7.0 wheel,
with no system install [verified locally].

**The test tutorial is real.** It's the 6-step GitHub workflow "create label `needs-docs`" (dev DB workflow `aeeead80`,
current version), with its recorded action time per step (`end_ms - start_ms`) and its instruction texts, voiced by
ljspeech-medium.

### What sets a step's length today

- The compiler sizes a scene as `max(recorded action, estimateSpeechDurationMs(text))`, where the estimate is
  **375 ms per word + 400 ms**, clamped to 1.5–14 s [verified: `packages/tutorial-compiler/src/timing/speech.ts`,
  `compiler.ts`]. It already takes overrides: `options.stepDurations[step_seq]` and `options.wordTimings[step_seq]`
  [verified: `compiler.ts`]. So Piper's real lengths can go in without changing the compiler.
- The player gets away with the estimate because it **holds the step until speech ends** + 400 ms (#267). A video
  can't hold: the timeline is fixed before rendering.
- **The estimate is too short for most real steps** [verified locally, 104 texts, estimate vs Piper clip + 400 ms]:

  | Voice | Steps where the estimate is too short | Worst shortfall |
  |---|---|---|
  | ljspeech-medium | 75 / 104 | 3.98 s |
  | norman-medium | 56 / 104 | 3.94 s |
  | kristin-medium | 65 / 104 | 3.26 s |
  | ljspeech-high | 71 / 104 | 4.34 s |

  The label flow, step 5 (`enter “#d73a4a” in “Color”`): estimate 3775 ms, real speech **5608 ms**.

- **Recorded action times are tiny next to narration.** In the label flow, actions take 239–486 ms except the first
  navigate (5956 ms). Speech takes 1.1–5.6 s. Narration sets the pace of almost every scene.

### Scene timeline (label flow, 30 fps) [verified locally]

`scene = max(action_ms, 300 ms lead-in + clip + 400 ms hold)`, rounded **up** to whole frames:

| Step | Action | Action ms | Speech ms | Compiler estimate | Scene | Frames |
|---|---|---|---|---|---|---|
| 1 | navigate | 5956 | 1718 | 5956 | 5967 | 179 |
| 2 | click | 486 | 1057 | 1525 | 1767 | 53 |
| 3 | fill | 298 | 3553 | 3775 | 4267 | 128 |
| 4 | fill | 239 | 4075 | 4525 | 4800 | 144 |
| 5 | fill | 287 | 5608 | **3775** | 6333 | 190 |
| 6 | click | 352 | 3878 | **3400** | 4600 | 138 |

Total 27.7 s.

### Joining the clips [verified locally]

Two ways to build one narration track with each clip at its scene start + 300 ms:

- **A. Place samples in Python** (silence between, `numpy`), then one AAC encode (96 kb/s).
- **B. FFmpeg only:** `adelay` per clip + `amix=normalize=0` + `apad`.

Then the track was decoded again to find where speech actually starts in each scene, compared with where it should
(scene start + lead-in + the clip's own leading silence):

| | 6 scenes | 60 scenes (flow × 10, 4 min 40 s) |
|---|---|---|
| A, WAV | ≤ 0.7 ms | ≤ 0.7 ms |
| A, AAC | ≤ 0.7 ms | ≤ 0.7 ms |
| B, AAC | ≤ 0.7 ms | ≤ 4.3 ms |
| Encode time A / B | 0.45 / 0.68 s | 2.4 / 2.6 s |

- Both are sample-accurate. AAC adds ~40 ms of padding at the **end** (27 733 → 27 771 ms) but doesn't shift starts:
  FFmpeg writes the encoder delay into the MP4 edit list.
- **What does drift is frames vs milliseconds.** If the audio follows the unrounded millisecond timeline while
  video scenes are rounded to frames, speech starts **85 ms early by step 6 and 1067 ms early by step 60**. Scene
  starts must be computed **once, in frames**, and the audio placed from those frame starts.
- Remotion places audio per `<Sequence>` (`from` in frames) and mixes it during render [unverified: Remotion docs
  not checked here; that's Nachiketha's #118]. If so, per-step clips need no joining step at all.
- Synthesizing the 6 clips took 13 s in this run, against ~0.5 s in `piper_bench.py`. That was the same laptop slowing
  background processes (see the threads finding in `phase-5-vishwas-piper-tts.md`), not the pipeline.

## Recommendation

Decided by Vishwas on 2026-11-01:

1. **Clips + manifest, no premixed track.** `tts/` stores one WAV per step and a narration manifest per workflow
   version: `{voice, sample_rate, steps: [{step_seq, text_sha256, audio_key, duration_ms, words: WordTiming[]}]}`.
   Clips are cached by `(voice, sha256(text))`, so a new version only voices the steps whose text changed. Remotion
   puts each clip in its scene's `<Sequence>`. Joining (A above) is a 0.5 s fallback if Remotion's audio mixing
   misbehaves.
2. **Scene length = `max(recorded action, 300 ms + clip + 400 ms)`, rounded up to whole frames at 30 fps**, passed to
   the compiler as `stepDurations` and the word timings as `wordTimings` (offset by the 300 ms lead-in, so they stay
   relative to the scene start, as the contract says). The 400 ms matches the player's narration hold (#267).
3. Every place that turns ms into a position (scene start, chapter, caption cue) uses the **same frame-snapped
   starts**. The spec already says `frame = round(ms / 1000 * fps)`; snapping durations up before summing keeps that
   lossless.
4. Narration is generated **inside the export job**, through a `Narrator` port that `tts/` implements (not when a
   workflow is saved).

## Open questions

- Whether the compiler (Nachiketha's package) or the export job turns the manifest into `stepDurations`: a small
  interface point for #120/#122. The manifest has everything either needs.
- Lead-in (300 ms) and hold (400 ms) are guesses tuned to the player; check them by watching the first real export.
- Sensitive steps: the instruction text is already masked, so the voice never says a secret. Keep a test for it.

## Links
- `packages/tutorial-compiler/src/timing/speech.ts`, `compiler.ts`
- `contracts/schemas/tutorial-spec.schema.json` (`Caption.words`, `fps`, frame rule)
- https://ffmpeg.org/ffmpeg-filters.html#adelay, #amix, #apad
