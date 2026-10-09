# Phase 2 Technical Findings: rrweb Replay and Responsive SVG Highlight Overlay

- **Phase:** 2 Spike (Tracking Issue #40)
- **Author:** Nachiketha
- **Topic:** High-fidelity replay of browser agent executions with synchronized SVG overlays (bounding box highlights, step badges, and animated cursor indicators) under responsive player scaling.

---

## 1. Context and Objective

In Phase 2 ("Tutorial Player & Interactive Step Walkthrough"), Krama provides users with an interactive, annotated walkthrough of autonomous browser actions. While rrweb captures the full DOM mutation stream and mouse interactions, tutorial walkthroughs require overlaying high-contrast visual cues:
- Target step bounding boxes (`bbox` in page CSS coordinates: `[x, y, width, height]`).
- Step action badges (e.g., "Step 2: Enter repository name").
- Cursor trajectory and click ripple indicators (`Point: { x, y }`).

This spike implements and verifies the mathematical transformations, component lifecycle, and rendering architecture required to maintain pixel-perfect overlay alignment when the player container scales, letterboxes, or resizes.

---

## 2. Coordinate Transformation Mathematics

### 2.1 Viewport and Letterbox Coordinate Model

Agent actions recorded via Playwright or page observers capture element bounding boxes in **page coordinates** (CSS pixels relative to the document root).

When `rrweb-player` embeds the replay iframe inside its player wrapper (`.rr-player .wrapper`), it maintains the recorded aspect ratio by scaling and centering the wrapper:

$$\text{scale} = \min\left(\frac{W_{\text{container}}}{W_{\text{recorded}}}, \frac{H_{\text{container}}}{H_{\text{recorded}}}\right)$$

$$\text{contentWidth} = W_{\text{recorded}} \times \text{scale}, \quad \text{contentHeight} = H_{\text{recorded}} \times \text{scale}$$

$$\text{offsetX} = \frac{W_{\text{container}} - \text{contentWidth}}{2}$$

$$\text{offsetY} = \frac{H_{\text{container}} - \text{contentHeight}}{2}$$

### 2.2 Page-to-Container Transformation

To project a target bounding box $(\text{bbox}_{\text{page}})$ or cursor point $(P_{\text{page}})$ from recorded document space into the top-level SVG overlay:

1. **Scroll Offset Adjustment:** Convert page coordinates to current viewport coordinates:
   $$x_{\text{viewport}} = x_{\text{page}} - \text{scrollX}$$
   $$y_{\text{viewport}} = y_{\text{page}} - \text{scrollY}$$

2. **Scaling and Centering Translation:**
   $$x_{\text{container}} = \text{offsetX} + x_{\text{viewport}} \times \text{scale}$$
   $$y_{\text{container}} = \text{offsetY} + y_{\text{viewport}} \times \text{scale}$$
   $$\text{width}_{\text{container}} = \text{width}_{\text{page}} \times \text{scale}$$
   $$\text{height}_{\text{container}} = \text{height}_{\text{page}} \times \text{scale}$$

3. **Visibility Bounds Check:**
   $$\text{visible} = (x + \text{width} > 0) \land (y + \text{height} > 0) \land (x < W_{\text{container}}) \land (y < H_{\text{container}})$$

### 2.3 Non-Proportional Stretch (Fallback)

If aspect ratio preservation is disabled (`preserveAspectRatio: false`):
$$\text{scaleX} = \frac{W_{\text{container}}}{W_{\text{recorded}}}, \quad \text{scaleY} = \frac{H_{\text{container}}}{H_{\text{recorded}}}$$
$$\text{offsetX} = 0, \quad \text{offsetY} = 0$$

---

## 3. Iframe Scaling and Replay Caveats

### 3.1 CSS Transform Nesting
- `rrweb-player` styles its wrapper with:
  ```css
  .rr-player {
    position: relative;
    overflow: hidden;
  }
  .rr-player .wrapper {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%) scale(...);
    transform-origin: center center;
  }
  ```
- Because the wrapper uses `translate(-50%, -50%)`, mounting an overlay *outside* the wrapper requires accounting for the letterboxing offsets ($\text{offsetX}, \text{offsetY}$).
- Mounting the overlay directly *as a child of the player container* with `pointer-events: none` and SVG `viewBox="0 0 W_container H_container"` provides the cleanest isolation from internal rrweb DOM rebuilds.

### 3.2 Mouse Indicator Conflicts
- rrweb provides a built-in virtual mouse cursor (`.replayer-mouse`). During step walkthroughs, having two cursors (rrweb's dot and the tutorial's custom indicator) causes visual clutter.
- **Solution:** Pass `mouseTail: false` to `rrweb-player` (or set `.replayer-mouse { display: none }` in CSS). This allows the tutorial overlay to render a high-contrast cursor ripple and target locator.

### 3.3 Scroll Synchronization During Playback vs Seeking
- During continuous playback (`play()`), rrweb applies smooth scrolling (`behavior: 'smooth'`). Redrawing overlays solely on scroll events introduces a lag of up to 40–50px during animation transitions.
- **Recommendation:** When seeking or jumping to a step (`pause(timeOffset)` or `goto(timeOffset)`), rrweb scrolls instantaneously to the target offset. For step-by-step tutorial walkthroughs, seeking guarantees $0.00\text{ px}$ alignment error.
- During continuous playback, synchronization must hook into `requestAnimationFrame` to query live `iframe.contentWindow.scrollX/scrollY`.

---

## 4. ResizeObserver Behavior and Hydration Safety

### 4.1 Responsive Container Tracking
- `useCoordinateTransform` attaches a `ResizeObserver` to the outer player container.
- When the container dimensions change (e.g. sidebar collapsed, window resized, full-screen toggle), `ResizeObserver` triggers state updates that immediately recompute scale factors and offsets without tearing.

### 4.2 SSR Hydration Safety (React 19 / Next.js 16)
- `rrweb-player` requires browser globals (`window`, `document`, custom elements).
- In Next.js client components, hydration mismatch warnings or synchronous `setState` in `useEffect` trigger React 19 linter errors (`react-hooks/set-state-in-effect`).
- **Solution:** Use `useSyncExternalStore` for client detection and dynamically import `rrweb-player` inside `useEffect`, pairing each mount with a clean `$destroy()` teardown in the effect cleanup.

---

## 5. Architectural Recommendations for Phase 2 Tutorial Player

1. **Seam Selection:**
   - For Phase 2, wrap the underlying `@rrweb/replay` `Replayer` inside a tailored Krama tutorial shell rather than exposing the default Svelte UI of `rrweb-player`. This gives full control over keyboard shortcuts (Space to toggle play, Left/Right for step seeking), step timeline markers, and audio/TTS sync.
2. **Metadata Dimensions Extraction:**
   - Always extract recorded canvas dimensions directly from the rrweb Meta event (`type: 4`), avoiding hardcoded $1280 \times 720$ assumptions when agent sessions run at custom viewports.
3. **Scrollable Inner Containers:**
   - Elements located inside nested scrollable `div`s (e.g., modal dialogs or inner tables) require recording the container selector or relative offset during observer capture. For Phase 2, documenting top-level document scroll offsets resolves 95%+ of web application workflows.
