# 0006 — Remotion video rendering: screenshot-based frames over rrweb replay

- **Status:** accepted
- **Deciders:** Nachiketha (spike, benchmarks and recommendation), Vishwas (review and alignment in `phase-5-decisions-alignment.md` D7–D10)
- **Issue:** #123 · Spike & Research: [`phase-5-nachiketha-rrweb-vs-screenshots.md`](../research/phase-5-nachiketha-rrweb-vs-screenshots.md) (#118)

## Context

Phase 5 exports Verified Workflows as standalone 1080p MP4 videos (in `landscape` 1920×1080 and `portrait` 1080×1920 presets at 30 fps) with Piper narration, camera zoom, cursor glides, bounding-box highlights, and subtitle captions.

In the interactive web player (`frontend/components/player/RecordedPage.tsx`), the real web UI is presented by mounting an `rrweb.Replayer` inside an iframe and pausing it at each step's time offset (`timeOffsetMs`).

For offline video export with Remotion (`packages/video-exporter`), we had to decide how the real UI gets into the video:
1. **Approach A:** Have Remotion drive an `rrweb.Replayer` frame-by-frame inside headless Chromium tabs, seeking via `replayer.goto(timeMs)`.
2. **Approach B:** Render each scene in the Remotion composition using the step's settled screenshot (`step.screenshot_path`) stored in the `ArtifactStore`, animating the camera, cursor, ripple, and highlight on top as native React/SVG overlays.

A spike was conducted comparing both approaches on a reference 6-step tutorial on Nachiketha's 16GB CPU-only laptop.

### Spike Results

| Metric | Approach A: rrweb-in-Remotion | Approach B: Screenshot Frames + Vector Overlays |
|---|---|---|
| **Render time (30s video, 900 frames)** | 98–135 s (~3.3–4.5× slower than real time) | **26–32 s (~0.9–1.0× real time on CPU)** |
| **Chromium RAM (per tab)** | 620–780 MB | **190–230 MB** |
| **Total render RAM (`concurrency: 4`)** | > 2.8 GB (risk of memory thrashing on 16GB) | **~1.2 GB (safe & lightweight)** |
| **Visual stability** | Layout reflow jitter, web font loading delays, blank frame anomalies | **100% deterministic (pixel-perfect raster frames)** |
| **Credential masking** | Requires in-memory DOM redaction rules | **Guaranteed (pre-masked by observer/policy layer)** |
| **Portrait layout (9:16)** | Complex CSS iframe clipping & coordinate mapping | **Direct CSS `transform` / `object-fit` / camera pan** |

## Decision

1. **Remotion compositions render scenes from step screenshots, not `rrweb` replay.** Each step in the `TutorialSpec` renders its background image using the pre-captured, pre-masked screenshot from `step.screenshot_path` (served by `ArtifactStore` / local filesystem).
2. **All interactive tutorial elements are rendered as vector SVG and React components over the screenshot:**
   - The cursor glides smoothly along a cubic-bezier path from the previous position to the step target.
   - The click ripple animates radial expansion and fade at `cursor.click_ms`.
   - The highlight box outlines the target element at `highlight.bbox` with high-contrast accent styling.
   - The camera pans and zooms using CSS `transform: translate3d(...) scale(...)`.
3. **Framing & Aspect Ratio Presets (Decisions D6–D8):**
   - **`landscape` (1920×1080):** Centers the 1280×800 (16:10) viewport with neat 96 px side bars (`#0b0f19`). Camera zooms into the target element using `scene.camera` (scale up to 3.0×, 450 ms ease).
   - **`portrait` (1080×1920):** Follows the highlight dynamically. For steps with an element, the camera centers a 9:16 window on `highlight.bbox` with minimum zoom `scale >= 1.6×` so input fields, buttons, and text are sharp and legible on mobile screens. Panning between steps uses smooth cubic-bezier easing. Overview steps show the full viewport fitted horizontally.
4. **Captions and Narration:**
   - Spoken narration clips from the Piper `NarrationManifest` are mapped to frame-snapped scene sequences via `plan_scenes`.
   - Subtitle captions are burned into the bottom of the video with word-level highlighting based on `WordTiming`, and exported as a matching `.vtt` WebVTT sidecar.

## Alternatives considered

- **Driving `rrweb.Replayer` inside Remotion:** Rejected. It is 4–6× slower, consumes 3× more RAM, introduces asynchronous frame drops in headless Chromium, and risks unhandled iframe sandboxing errors in Node environments.
- **`rrvideo` CLI tool (Puppeteer screencast):** The rrweb project's CLI tool converts recordings into WebM/MP4. Rejected because it does not support Remotion's React composition model, camera zoom effects, burned-in karaoke captions, chapter metadata, intro/outro cards, or dual 16:9 / 9:16 aspect ratios.
- **Raw HTML snapshot rendering:** Storing and re-rendering full HTML DOM snapshots per step instead of PNG screenshots. Rejected because external stylesheets and fonts break offline, and rendering time is substantially higher than static PNG rasterization.

## Consequences

- **Easier:** Render throughput is fast (~1.0× real time on a CPU-only laptop). Export jobs run stably in background arq workers within standard memory limits.
- **Safe:** Credential masking applied during run capture is preserved without any possibility of plaintext credential leakage into exported MP4 videos.
- **Consistent:** The video composition directly consumes the exact same `TutorialSpec` JSON generated by `@krama/tutorial-compiler`, ensuring visual alignment between the web player and the exported video.
