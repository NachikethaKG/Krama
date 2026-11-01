# Phase 5: Video export

**Goal:** export any tutorial as an MP4 (16:9 and 9:16) with narration, captions and chapter markers, from the **same** TutorialSpec the player uses. CPU rendering only.

**Release tag:** `v1.2`

**Who builds what**
- **Vishwas:** narration audio (Piper TTS on CPU), the export API, video storage.
- **Nachiketha:** the Remotion exporter package and the backend export jobs (`export/`) that drive it.

---

## Research before starting

> **Research chat prompts:** copy yours from [#117 (Vishwas)](https://github.com/NachikethaKG/Krama/issues/117) or [#118 (Nachiketha)](https://github.com/NachikethaKG/Krama/issues/118), or run `just research-prompt 5 <name>`. Together questions: [#119](https://github.com/NachikethaKG/Krama/issues/119). How it works: [`docs/research/`](../research/README.md).

**Vishwas**
- **Piper TTS:** voice quality, speed on CPU, and the **license of each voice model** (they differ). Can Piper output word or phoneme timings, so captions match the audio?
- **Audio pipeline:** generate one clip per step, then join them with FFmpeg. How do you make step timing follow narration length?
- **Storage:** typical MP4 size per minute at 1080p. When should we move from local files to S3/MinIO?

**Nachiketha**
- **Remotion license:** check the current terms. Remotion is free only for individuals and small companies; confirm what applies to us.
- **Rendering on CPU:** `@remotion/renderer` from Node. Render time per minute of video on a 16GB CPU-only laptop; concurrency and memory settings.
- **Rendering rrweb inside Remotion:** can the rrweb replayer be driven frame by frame inside a Remotion composition, or do we render from screenshots instead?
- **Video features:** FFmpeg chapter metadata, burned-in vs sidecar captions (`.vtt`), 9:16 layouts that keep the highlighted element visible.

**Together**
- Decide the presets (resolution, aspect ratios, intro/outro) and whether exports include the cursor and zoom effects exactly as in the player.

**Decided (2026-11-01):** research and the together decisions are in
[`phase-5-decisions-alignment.md`](../research/phase-5-decisions-alignment.md) (D1–D20): voice and Piper worker
([ADR 0004](../adr/0004-piper-voice-and-license.md)), narration clips + manifest, scene timing, presets
`landscape` 1920×1080 / `portrait` 1080×1920, export statuses and ports, retention, and storage
([ADR 0005](../adr/0005-object-storage-seaweedfs.md): MinIO is archived, SeaweedFS later).

---

## Sprint 5.1: render

| Vishwas | Nachiketha |
|---|---|
| `ports/`: `Narrator` port (contract PR), then `tts/` + `tts-worker/`: Piper narration per step + timings | `packages/video-exporter`: Remotion composition from TutorialSpec (cursor, highlights, zoom, captions) |
| ADR: Piper voice choice and license ([0004](../adr/0004-piper-voice-and-license.md)) | Spike: rrweb-in-Remotion vs screenshot-based frames (ADR) |

## Sprint 5.2: export pipeline

| Vishwas | Nachiketha |
|---|---|
| Contract PR (`Export`, `exports`, `ExportQueue`/`ExportStore` ports), then `api/`: `POST /workflows/{id}/exports`, export status, download, captions | `export/`: export job (arq) that calls the renderer, with progress events |
| `storage/`: video artifacts, cleanup (30 days, `EXPORTS_MAX_GB`) | Frontend: Export MP4 dialog (preset, aspect ratio), progress, download; chapter markers in the file |

## Exit criteria
- Export an MP4 of a 6-step tutorial with narration and chapters on Nachiketha's laptop.
- 16:9 and 9:16 both keep the highlighted element in frame.
- Rendering time is documented for both laptops.
- The narration uses the public-domain voice from ADR 0004.
- Exports past the retention rule are cleaned up (#125).
