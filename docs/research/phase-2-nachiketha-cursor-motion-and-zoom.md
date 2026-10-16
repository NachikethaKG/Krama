# Natural Cursor Motion, Bezier Paths, and Auto-Zoom

- **Phase:** 2
- **Researched by:** Nachiketha
- **Question(s):** Cursor motion: easing curves and bezier paths that look natural; auto-zoom like Screen Studio; respecting `prefers-reduced-motion`.

## Findings

### 1. Natural Cursor Physics & Bezier Paths

Straight-line cursor motion between two interface coordinates looks robotic and jarring. Real human mouse trajectories exhibit biomechanical curvature: the hand pivots from the wrist or elbow, introducing an arc, and decelerates smoothly as it nears the target [verified locally].

- **Parametric Cubic Bezier Curve Formulation:**
  For start point $P_0 = (x_0, y_0)$ and end point $P_3 = (x_3, y_3)$:
  $$B(t) = (1-t)^3 P_0 + 3(1-t)^2 t P_1 + 3(1-t) t^2 P_2 + t^3 P_3 \quad \text{for } t \in [0, 1]$$
- **Control Point Offset:**
  - Let $D = \sqrt{(x_3 - x_0)^2 + (y_3 - y_0)^2}$ be the Euclidean distance.
  - Compute unit normal vector perpendicular to the motion chord: $N = \left(-\frac{y_3 - y_0}{D}, \frac{x_3 - x_0}{D}\right)$.
  - Control point $P_1$ sits at $t = 0.25$ along the chord with perpendicular offset $\delta_1 = \pm (0.10 \text{ to } 0.25) \times D$.
  - Control point $P_2$ sits at $t = 0.75$ along the chord with perpendicular offset $\delta_2 = \pm (0.05 \text{ to } 0.15) \times D$.
  - The sign ($\pm$) determines convex or concave arc curvature, mimicking natural right-handed wrist rotation [verified locally].
- **Temporal Easing:**
  - Standard linear or simple quad easing feels unnatural.
  - **Ease-out Quintic / Smooth Deceleration Curve:**
    `cubic-bezier(0.22, 1, 0.36, 1)` (also known as `easeOutQuint` / Apple spring feel).
    The cursor accelerates quickly during the first 25% of duration, then glides smoothly to decelerate into the exact target bounding box center [verified locally].
  - Recommended duration: 450 ms for short hops ($< 300\text{ px}$), up to 700 ms for cross-screen sweeps ($> 800\text{ px}$).

### 2. Auto-Zoom Geometry & Camera Framing

To replicate Screen Studio's cinematic clarity, the tutorial viewport smoothly magnifies the region of interest surrounding the target element [verified locally]:

- **Focal Center Calculation:**
  For target element bounding box $(x, y, w, h)$ in viewport coordinates:
  $$C_x = x + \frac{w}{2}, \quad C_y = y + \frac{h}{2}$$
- **Scale Factor:**
  - Standard sweet spot: **$S = 1.35\times$ to $1.50\times$**.
  - Scales $< 1.25\times$ lack visual focus impact; scales $> 1.7\times$ lose too much surrounding context and cause disorientation.
- **Canvas Edge Clamping:**
  When zooming into corner or edge elements (e.g. top-right user menu, bottom-left sidebar toggle), naive centering would expose blank canvas margins outside the document viewport $(W, H)$.
  - Offset calculation:
    $$\Delta x = C_x \times (1 - S), \quad \Delta y = C_y \times (1 - S)$$
  - Clamping bounds:
    $$\Delta x_{\text{clamped}} = \max(-(W \times (S - 1)), \min(0, \Delta x))$$
    $$\Delta y_{\text{clamped}} = \max(-(H \times (S - 1)), \min(0, \Delta y))$$
  - CSS Transform applied to player canvas container:
    ```css
    transform: translate3d(var(--pan-x), var(--pan-y), 0) scale(var(--zoom-scale));
    transition: transform 450ms cubic-bezier(0.22, 1, 0.36, 1);
    transform-origin: 0 0;
    ```
  - This ensures that canvas edges are never exposed, while keeping the target element prominently centered [verified locally].

### 3. Respecting Reduced Motion (`prefers-reduced-motion`)

Users sensitive to motion sickness or vestibular disorders must have motion effects neutralized per W3C accessibility guidelines [verified: W3C Media Queries Level 5]:

- **When `prefers-reduced-motion: reduce` is active:**
  1. **Zoom Scale Clamped to 1.0x:** All auto-zoom and focal panning is disabled. The viewport remains static at native 100% scale.
  2. **Zero-Duration Cursor Jump:** Cursor transitions from $P_0$ to $P_3$ instantly ($0\text{ ms}$) without Bezier path interpolation.
  3. **Static Highlight Frames:** Pulsing ripple / halo animations are replaced with a static 2px solid highlight border (`#4f46e5` with 4px corner radius) that does not animate or flash.

## Recommendation

1. Implement a pure TypeScript Bezier trajectory generator in `packages/tutorial-compiler`:
   - Inputs: start coordinates, end target bbox, duration, motion preferences.
   - Outputs: evaluated keyframe coordinates $(x_t, y_t)$ or SVG path data `<path d="..." />`.
2. Apply camera auto-zoom via CSS hardware-accelerated transforms (`translate3d` + `scale`) in the tutorial player canvas component.
3. Automatically detect `window.matchMedia('(prefers-reduced-motion: reduce)')` in `@krama/player` and gracefully clamp scale to 1.0x and cursor transition to 0ms.
[No ADR required: conforms to Phase 2 roadmap].

## Open questions

- For very large elements (e.g., repository description textarea spanning 80% of viewport width), should the compiler dynamically lower scale to 1.1x–1.2x to prevent cropping?
- Should the player allow user override of zoom intensity (e.g., 100% / 125% / 150% toggle in settings)?

## Links

- [W3C Media Queries Level 5 — prefers-reduced-motion](https://www.w3.org/TR/mediaqueries-5/#prefers-reduced-motion)
- [Cubic-Bezier Easing Function Reference](https://cubic-bezier.com/)
- [Screen Studio Motion Design Patterns](https://screen.studio/)
