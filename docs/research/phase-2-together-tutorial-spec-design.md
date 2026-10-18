# Tutorial Spec Architecture: Bridging Interactive DOM Replay and Deterministic Remotion Video

- **Phase:** 2 (Compiler Sprint 2.1)
- **Researched by:** Vishwas & Nachiketha (agreed joint design outcome for #70)
- **Question(s):** Design `tutorial-spec.schema.json`: scenes, cursor path, highlights, zooms, captions, timings. Look at how `rrweb-player` and Remotion compositions consume time, since Phase 5 reuses the same spec.

---

## 1. Executive Summary & Design Principles

The Tutorial Specification (`tutorial-spec.schema.json`) serves as the universal canonical data structure produced by the pure TypeScript compiler (`packages/tutorial-compiler`). It compiles a recorded `Verified Workflow` into an actionable visual timeline.

A fundamental design requirement is **dual-engine consumption**:
1. **Interactive Web Player (Sprint 2.2):** Replays DOM mutations via `@rrweb/types` and canvas overlays with interactive pauses at user interaction points.
2. **Deterministic Video Exporter (Phase 5):** Generates polished MP4 videos via Remotion where time is quantized strictly into discrete rendering frames.

By unifying time representation in integer milliseconds and anchoring spatial geometry to absolute page CSS pixels, both engines consume the exact same specification without precision loss, spatial misalignment, or code duplication [verified: architecture.md].

---

## 2. Time Duality: Continuous DOM Replay vs. Discrete Frame Video

A core architectural challenge discovered during joint research is the fundamental divergence in how `rrweb-player` and `Remotion` process time:

| Dimensional Aspect | Interactive Player (`rrweb-player`) | Video Exporter (`Remotion`) |
|---|---|---|
| **Underlying Time Base** | Real-time continuous wall-clock / `requestAnimationFrame` [verified locally] | Discrete integer frame indices (`frame = Math.round(ms / 1000 * fps)`) [verified locally] |
| **Frame Rate** | Variable (dependent on display refresh rate, 60Hz/120Hz/144Hz) [verified: W3C HTML] | Fixed & deterministic (pinned at 30 fps or 60 fps) [verified: Remotion docs] |
| **Interaction Pauses** | Halts at interaction moments awaiting human click/fill or step progression [verified locally] | Converted into scripted, deterministic settle/dwell duration (e.g. 500–800 ms) [verified locally] |
| **Seeking Mechanics** | Fast-forwards by applying historical snapshot diffs from nearest `FullSnapshot` [verified: rrweb docs] | Directly evaluates frame state via `useCurrentFrame()` and `interpolate()` [verified: Remotion docs] |
| **Narration & Audio** | Driven asynchronously via Web Speech API `SpeechSynthesis` boundaries [verified locally] | Muxed synchronously onto the video timeline via Remotion `<Audio />` or FFmpeg [verified: Remotion docs] |

### The Integer Millisecond Trade-Off

- **Why milliseconds?**
  - Storing Remotion frames directly in the spec would tightly couple the specification to an arbitrary rendering frame rate (e.g., 30 fps) and break variable-rate continuous playback in `rrweb-player`.
  - Conversely, storing fractional seconds (floats like `1.2485s`) causes subtle IEEE 754 rounding errors that drift out of sync across multi-minute, multi-step tutorials.
  - Storing integer milliseconds (`ms: integer, minimum: 0`) provides an exact, lossless standard. Remotion transforms milliseconds into frames on-the-fly:
    $$\text{frame} = \text{Math.round}\left(\frac{t_{\text{ms}}}{1000} \times \text{fps}\right)$$
  - At 30 fps ($\Delta t \approx 33.3\text{ ms}$) and 60 fps ($\Delta t \approx 16.7\text{ ms}$), integer millisecond precision provides sub-frame resolution with at most $\pm 0.5$ frame rounding jitter, eliminating any temporal drift [verified locally].

---

## 3. The Scene Model

A workflow step represents a single coherent atomic action (e.g., click link, fill input, select dropdown). In `tutorial-spec.schema.json`, each step is compiled into a discrete `Scene`:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Scene Duration (duration_ms = 1600ms)                                  │
├────────────────────┬─────────────────────────────┬─────────────────────┤
│ Beat 1: Orient     │ Beat 2: Act                 │ Beat 3: Settle      │
│ 0ms - 400ms        │ 400ms - 1100ms              │ 1100ms - 1600ms     │
│ Camera Zoom & Pan  │ Cubic Bezier Cursor Glide   │ Click Ripple & Dwell│
│ Caption Begins     │ Synchronized Word Timings   │ Replay Execution    │
└────────────────────┴─────────────────────────────┴─────────────────────┘
```

Each scene encapsulates:
1. **Scene Metadata (`id`, `step_index`, `title`, `duration_ms`):** Unique step sequence identifier and total duration budget.
2. **Camera Keyframe (`camera`):**
   - `scale`: Magnification factor ($1.35\times$ to $1.50\times$).
   - `center_x`, `center_y`: Focal center coordinates in page CSS pixels.
   - `easing`: Motion easing curve, default `cubic-bezier(0.22, 1, 0.36, 1)`.
   - `pan_duration_ms`: Duration of zoom/pan transition.
3. **Cursor Path (`cursor`):**
   - `path`: Four control points $[P_0, P_1, P_2, P_3]$ defining the parametric cubic Bezier curve.
   - `start_ms`, `end_ms`: Cursor glide start and arrival times.
   - `click_ms`: Exact millisecond timestamp when the click ripple triggers.
   - `click_type`: Action type (`single`, `double`, `none`).
   - `ripple`: Click ripple configuration (`enabled`, `radius`, `color`).
4. **Highlight Bounding Box (`highlight`):**
   - `bbox`: $[x, y, w, h]$ bounding box in page CSS pixels.
   - `style`: Visual styling mode (`pulsing_ring`, `solid_box`, `spotlight`).
   - `padding`: Outset padding in CSS px.
   - `color`: Hex or rgba accent color.
5. **Caption & Narration (`caption`):**
   - `text`: Complete instruction / narration text.
   - `words`: Word-level timing tokens $[(w_0, t_{\text{start}}, t_{\text{end}}), \dots]$ to drive synchronous karaoke-style subtitle highlighting.
6. **Underlying Recording Slice (`rrweb_slice`):**
   - `start_timestamp`, `end_timestamp`: Millisecond boundaries within the session's recorded rrweb event stream.
   - `baseline_snapshot_event_index`: Index of the preceding `FullSnapshot` needed to render the slice without visual corruption.
7. **Synchronous Scroll State (`scroll`):**
   - `x`, `y`: Absolute window scroll position at the moment of action execution, ensuring `viewport_box = page_bbox - scroll` is calculated without depending on asynchronous DOM scroll events [verified locally: `phase-2-vishwas-coordinates.md`].

---

## 4. Coordinate Space and DPR Invariance

Spatial alignment across diverse browser environments, devices, and video rendering viewports relies on strict coordinate standards:

1. **Page Coordinates as Canonical Truth:**
   - Elements are stored in absolute page CSS pixels:
     $$\text{bbox}_{\text{page}} = [x_{\text{viewport}} + \text{scrollX}, y_{\text{viewport}} + \text{scrollY}, w, h]$$
   - Viewport-relative positions shift during user scrolling, but page coordinates remain invariant across re-renders [verified locally: `phase-2-vishwas-coordinates.md`].
2. **Device Pixel Ratio (DPR) Invariance:**
   - Playwright's `locator.bounding_box()`, CSS pixels, and rrweb mouse interaction events operate entirely in CSS pixels regardless of whether DPR is 1.0 (standard display) or 2.0 (Retina display) [verified locally: `phase-2-vishwas-coordinates.md`].
   - Physical bitmap pixel dimensions ($px_{\text{device}} = px_{\text{CSS}} \times \text{DPR}$) apply only when rasterizing screenshot images, never when executing DOM transforms or video canvas scaling.
3. **Canvas Edge Clamping:**
   - Auto-zoom scaling uses clamping offsets to ensure that zoomed viewports never expose blank space outside the documented page bounds:
     $$\Delta x_{\text{clamped}} = \max(-(W \times (S - 1)), \min(0, C_x \times (1 - S)))$$
     $$\Delta y_{\text{clamped}} = \max(-(H \times (S - 1)), \min(0, C_y \times (1 - S)))$$
     [verified locally: `phase-2-nachiketha-cursor-motion-and-zoom.md`]

---

## 5. Canonical JSON Schema (`tutorial-spec.schema.json`)

> **Superseded (2026-10-17):** the contract is now [`contracts/schemas/tutorial-spec.schema.json`](../../contracts/schemas/tutorial-spec.schema.json) (#71, PR #242): draft 2020-12, element fields nullable, `step_index` renamed `step_seq`, and more; the differences are listed in PR #242. The Draft-07 version below is kept as the research record. Its copies in `packages/tutorial-compiler/src/schema/` and `docs/specs/` were removed.

The schema conforms to **JSON Schema Draft-07** (`http://json-schema.org/draft-07/schema#`) for universal toolchain compatibility across TypeScript (via `json-schema-to-typescript`) and Python (via `jsonschema`):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "tutorial-spec.schema.json",
  "title": "TutorialSpec",
  "description": "Canonical specification for an interactive tutorial or video scene sequence (Phase 2 & Phase 5).",
  "type": "object",
  "required": [
    "version",
    "workflow_id",
    "title",
    "viewport",
    "fps",
    "total_duration_ms",
    "scenes"
  ],
  "additionalProperties": false,
  "properties": {
    "version": {
      "type": "string",
      "description": "Specification format version (e.g. '1.0')."
    },
    "workflow_id": {
      "type": "string",
      "format": "uuid",
      "description": "UUID of the source Verified Workflow."
    },
    "title": {
      "type": "string",
      "minLength": 1,
      "description": "Human-readable title describing the tutorial."
    },
    "description": {
      "type": "string",
      "description": "Optional extended description or task prompt."
    },
    "viewport": {
      "$ref": "#/definitions/Viewport"
    },
    "fps": {
      "type": "integer",
      "minimum": 1,
      "maximum": 120,
      "default": 30,
      "description": "Target frame rate for video rendering (Remotion export)."
    },
    "total_duration_ms": {
      "type": "integer",
      "minimum": 0,
      "description": "Total duration of the tutorial across all scenes in integer milliseconds."
    },
    "scenes": {
      "type": "array",
      "minItems": 1,
      "description": "Sequential scene specifications corresponding to workflow steps.",
      "items": {
        "$ref": "#/definitions/Scene"
      }
    }
  },
  "definitions": {
    "Viewport": {
      "type": "object",
      "description": "Recording viewport dimensions in CSS pixels and device pixel ratio.",
      "required": ["width", "height"],
      "additionalProperties": false,
      "properties": {
        "width": { "type": "integer", "minimum": 1 },
        "height": { "type": "integer", "minimum": 1 },
        "device_scale_factor": { "type": "number", "minimum": 0.5, "default": 1.0 }
      }
    },
    "Point2D": {
      "type": "object",
      "description": "2D coordinate point in page CSS pixels.",
      "required": ["x", "y"],
      "additionalProperties": false,
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" }
      }
    },
    "BoundingBox": {
      "type": "array",
      "description": "[x, y, width, height] in CSS pixels, page coordinates.",
      "items": [
        { "type": "number" },
        { "type": "number" },
        { "type": "number" },
        { "type": "number" }
      ],
      "additionalItems": false,
      "minItems": 4,
      "maxItems": 4
    },
    "Camera": {
      "type": "object",
      "required": ["scale", "center_x", "center_y"],
      "additionalProperties": false,
      "properties": {
        "scale": { "type": "number", "minimum": 1.0, "maximum": 3.0, "default": 1.35 },
        "center_x": { "type": "number" },
        "center_y": { "type": "number" },
        "easing": { "type": "string", "default": "cubic-bezier(0.22, 1, 0.36, 1)" },
        "pan_duration_ms": { "type": "integer", "minimum": 0, "default": 450 }
      }
    },
    "Ripple": {
      "type": "object",
      "required": ["enabled"],
      "additionalProperties": false,
      "properties": {
        "enabled": { "type": "boolean", "default": true },
        "radius": { "type": "number", "minimum": 0, "default": 24 },
        "color": { "type": "string", "default": "rgba(99, 102, 241, 0.4)" }
      }
    },
    "Cursor": {
      "type": "object",
      "required": ["path", "start_ms", "end_ms", "click_type"],
      "additionalProperties": false,
      "properties": {
        "path": {
          "type": "array",
          "items": { "$ref": "#/definitions/Point2D" },
          "minItems": 4,
          "maxItems": 4
        },
        "start_ms": { "type": "integer", "minimum": 0 },
        "end_ms": { "type": "integer", "minimum": 0 },
        "click_ms": { "type": ["integer", "null"], "minimum": 0 },
        "click_type": { "type": "string", "enum": ["single", "double", "none"], "default": "single" },
        "ripple": { "$ref": "#/definitions/Ripple" }
      }
    },
    "Highlight": {
      "type": "object",
      "required": ["bbox", "style"],
      "additionalProperties": false,
      "properties": {
        "bbox": { "$ref": "#/definitions/BoundingBox" },
        "style": { "type": "string", "enum": ["pulsing_ring", "solid_box", "spotlight"], "default": "pulsing_ring" },
        "padding": { "type": "number", "minimum": 0, "default": 8 },
        "color": { "type": "string", "default": "#4f46e5" }
      }
    },
    "WordTiming": {
      "type": "object",
      "required": ["word", "start_ms", "end_ms"],
      "additionalProperties": false,
      "properties": {
        "word": { "type": "string" },
        "start_ms": { "type": "integer", "minimum": 0 },
        "end_ms": { "type": "integer", "minimum": 0 }
      }
    },
    "Caption": {
      "type": "object",
      "required": ["text", "words"],
      "additionalProperties": false,
      "properties": {
        "text": { "type": "string" },
        "words": { "type": "array", "items": { "$ref": "#/definitions/WordTiming" } }
      }
    },
    "RrwebSlice": {
      "type": "object",
      "required": ["start_timestamp", "end_timestamp"],
      "additionalProperties": false,
      "properties": {
        "start_timestamp": { "type": "integer" },
        "end_timestamp": { "type": "integer" },
        "baseline_snapshot_event_index": { "type": ["integer", "null"] }
      }
    },
    "Scroll": {
      "type": "object",
      "required": ["x", "y"],
      "additionalProperties": false,
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" }
      }
    },
    "Scene": {
      "type": "object",
      "required": [
        "id",
        "step_index",
        "duration_ms",
        "camera",
        "cursor",
        "highlight",
        "caption",
        "rrweb_slice"
      ],
      "additionalProperties": false,
      "properties": {
        "id": { "type": "string" },
        "step_index": { "type": "integer", "minimum": 1 },
        "title": { "type": "string" },
        "duration_ms": { "type": "integer", "minimum": 0 },
        "camera": { "$ref": "#/definitions/Camera" },
        "cursor": { "$ref": "#/definitions/Cursor" },
        "highlight": { "$ref": "#/definitions/Highlight" },
        "caption": { "$ref": "#/definitions/Caption" },
        "rrweb_slice": { "$ref": "#/definitions/RrwebSlice" },
        "scroll": { "$ref": "#/definitions/Scroll" }
      }
    }
  }
}
```

---

## 6. Verification and Validation

The draft schema and its fixture (both since removed; see the note at the top of §5) have been verified programmatically against standard JSON Schema Draft-07 validators:
- Validated with Python `jsonschema.Draft7Validator`: passes with 0 errors [verified locally].
- Negative validation test confirmed: omission of required scene keys immediately trips `ValidationError` [verified locally].
- Dual storage location: committed to both `packages/tutorial-compiler/src/schema/tutorial-spec.schema.json` and mirrored in `docs/specs/tutorial-spec.schema.json`.

---

## 7. Recommendation

1. **Standardize on `tutorial-spec.schema.json`** as the single shared contract between compiler (Sprint 2.1), player (Sprint 2.2), and Remotion export (Phase 5).
2. **Implementation in Sprint 2.1:**
   - Vishwas's backend agent captures target element page bounding box, viewport, and scroll (`app/agent/executor.py`) [issue #72].
   - Nachiketha's tutorial compiler (`packages/tutorial-compiler`) takes a `Workflow` and outputs valid `TutorialSpec` JSON conforming strictly to this schema [issue #76].
3. **No ADR Required:** This implementation directly honors the frozen architecture in `docs/architecture.md` §1 ("Workflow → tutorial-compiler (TS, pure function) → TutorialSpec → Player / Remotion MP4") and adds no new runtime dependencies or infrastructure changes.

---

## 8. Links

- [docs/architecture.md](../architecture.md)
- [docs/phases/phase-2-interactive-tutorial.md](../phases/phase-2-interactive-tutorial.md)
- [phase-2-vishwas-coordinates.md](phase-2-vishwas-coordinates.md)
- [phase-2-nachiketha-cursor-motion-and-zoom.md](phase-2-nachiketha-cursor-motion-and-zoom.md)
- [phase-2-nachiketha-timing-alignment.md](phase-2-nachiketha-timing-alignment.md)
- [contracts/schemas/tutorial-spec.schema.json](../../contracts/schemas/tutorial-spec.schema.json) (the contract, #71)
- [contracts/fixtures/tutorial-spec/gitea-create-repo.json](../../contracts/fixtures/tutorial-spec/gitea-create-repo.json)
