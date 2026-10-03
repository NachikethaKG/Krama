# Phase 5: Video export

**Goal:** export any tutorial as an MP4 (16:9 and 9:16) with narration, captions and chapter markers, from the **same** TutorialSpec the player uses. CPU rendering only.

**Release tag:** `v1.2`

**Who builds what**
- **Vishwas:** narration audio (Piper TTS on CPU), the export API, video storage.
- **Nachiketha:** the Remotion exporter package and the backend export jobs (`export/`) that drive it.

---

## Research before starting

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

---

## Sprint 5.1: render

| Vishwas | Nachiketha |
|---|---|
| `tts/`: Piper narration per step + timings | `packages/video-exporter`: Remotion composition from TutorialSpec (cursor, highlights, zoom, captions) |
| ADR: Piper voice choice and license | Spike: rrweb-in-Remotion vs screenshot-based frames (ADR) |

## Sprint 5.2: export pipeline

| Vishwas | Nachiketha |
|---|---|
| `api/`: `POST /workflows/{id}/exports`, export status, download | `export/`: export job (arq) that calls the renderer, with progress events |
| `storage/`: video artifacts, cleanup of old exports | Frontend: Export MP4 dialog (preset, aspect ratio), progress, download; chapter markers in the file |

## Exit criteria
- Export an MP4 of a 6-step tutorial with narration and chapters on Nachiketha's laptop.
- 16:9 and 9:16 both keep the highlighted element in frame.
- Rendering time is documented for both laptops.
