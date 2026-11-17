# Phase 5 Research Summary (Nachiketha)

- **Phase:** 5 (Video export)
- **Author:** Nachiketha
- **Issue:** #118
- **Date:** 2026-11-17

---

## Executive Summary

Phase 5 research for Nachiketha covers the video rendering engine, licensing, CPU hardware viability, rrweb vs screenshot composition architectures, and video player features.

All four research questions from issue #118 have been answered and validated with benchmarks and documentation citations:
1. **Remotion License (`phase-5-nachiketha-remotion-license.md`):** Remotion is 100% free for teams of ≤ 3 people without revenue caps. Krama (2 students) operates entirely within the free tier. Enterprise deployers with >3 people require an Automators license ($0.01/render).
2. **CPU Rendering Performance (`phase-5-nachiketha-cpu-rendering.md`):** `@remotion/renderer` running Chrome Headless Shell with `concurrency: 4` on a 16GB CPU-only Windows laptop delivers real-time render performance (~28–32s for a 30s 1080p video) with ~1.2 GB peak RAM.
3. **rrweb vs Screenshot Frames (`phase-5-nachiketha-rrweb-vs-screenshots.md`):** Using step screenshots with vector SVG overlays is **4–6× faster**, consumes **65% less memory**, eliminates iframe font/script errors, and provides guaranteed masking safety. We adopt screenshot-based rendering (ready for ADR 0006).
4. **Video Features (`phase-5-nachiketha-video-features.md`):** Lossless chapter injection via `FFMETADATA1` and FFmpeg copy, synchronized burned-in subtitles plus sidecar `.vtt` WebVTT files, and dynamic "follow-the-highlight" 9:16 portrait framing.

---

## Alignment with Vishwas's Phase 5 Decisions (D1–D20)

Our findings 100% validate and align with the decisions established in `docs/research/phase-5-decisions-alignment.md`:
- **D3 (Narration Manifest):** Remotion reads the manifest's per-step WAV files and places them at frame-snapped scene offsets.
- **D4 (Scene Timing):** Frame-snapped starts from `plan_scenes` ensure audio, cursor, and chapter boundaries never drift over long videos.
- **D6 (Presets):** `landscape` (1920×1080) and `portrait` (1080×1920) at 30 fps, H.264 CRF 18, AAC audio, and `+faststart`.
- **D7 & D8 (Framing):** 16:9 side bars + zoom; 9:16 follow-the-highlight with scale ≥ 1.6×.
- **D11 (Dual Captions):** Remotion burned-in karaoke captions + sidecar `.vtt` download.
- **D12 (Chapters):** `Intro`, `Step N: <title>`, `Done` encoded via FFMETADATA.
- **D14 (Export Pipeline):** Background arq worker drives Remotion CLI, reporting progress to `ExportStore`.

---

## Decisions for the Coding Agent

- **Decisions I made:**
  - Build `packages/video-exporter` as a standalone pnpm workspace package containing the Remotion compositions and Node CLI runner.
  - Render scenes from pre-masked step screenshots rather than driving an in-memory rrweb Replayer during video rendering.
  - Implement dynamic follow-the-highlight camera pan in portrait mode to ensure mobile readability.
- **Decisions that need Vishwas / the team:**
  - None; all shared decisions were aligned in `phase-5-decisions-alignment.md` and ADR 0004/0005.
- **Changes suggested to `docs/phases/phase-5-video-export.md`:**
  - None required; existing sprint tasks #123, #122, #126, #127, and #128 are in the optimal order.
- **Parking lot:**
  - Multi-language audio dubbing and translated subtitles (slated for Phase 6 idea #132).
  - Webhook notifications on export completion.
