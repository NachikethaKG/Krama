# Drift detection signals: accessibility-tree diff vs DOM diff vs visual diff (pixelmatch vs SSIM)

- **Phase:** 4
- **Researched by:** Nachiketha (research and benchmark checks run on Nachiketha's reference machine: Windows 11, 16GB RAM, CPU-only, 2026-10-31; decisions by Nachiketha)
- **Question(s):** **Drift detection signals:** accessibility-tree diff vs DOM diff vs visual diff. Look at `pixelmatch` and SSIM; they must be CPU-friendly. Which signal catches a renamed button, a moved menu, a new dialog?

## Findings

Benchmark script, results JSON, and console output:
[`assets/phase-4-nachiketha-checks/`](assets/phase-4-nachiketha-checks/) (`drift_benchmarks.py`, `results-benchmarks.json`, `output.txt`).

### 1. Mechanics and Costs of the Three Signals

| Signal Layer | Tool / API | Reference Machine Cost [verified locally] | Sensitivity & Strengths | False Positive Vulnerability |
| :--- | :--- | :--- | :--- | :--- |
| **ARIA Snapshot** | Playwright `locator.ariaSnapshot()` | **~4.0 ms** (raw extraction); **<1 ms** (in-memory diff) | Pure semantic abstraction. Captures role, accessible name, and state (`disabled`, `expanded`). | **Extremely Low**. Completely ignores Tailwind class churn, CSS modules, dynamic React/Vue hydration IDs (`data-reactroot`, SSR hashes), and layout wrapper `<div>` tags. |
| **Bounding Box Delta** | Playwright `locator.boundingBox()` | **~4.3 ms** | Captures coordinate changes `[x, y, width, height]` and Euclidean centroid drift $\Delta d$. | **Low**. Differentiates stationary elements from layout adjustments via thresholding ($\le 30\text{px}$). |
| **Scoped Visual Diff** | `pixelmatch` / Pillow perceptual color delta | **~0.02 ms** (100x40px crop) to **15–30 ms** (dense component) | Perceptual per-pixel color delta ($L^*a^*b^*$ distance) with anti-aliasing filtering. | **Moderate**. Sensitive to font rasterization, subpixel anti-aliasing, and color themes. |
| *Avoided: DOM Tree Diff* | Full HTML AST diff | ~10–25 ms | Compares raw DOM nodes and attributes. | **Critically High**. Triggers false alarms on non-functional wrapper refactors, ephemeral test IDs, and hydration markers. |
| *Avoided: Full-Page SSIM* | Structural Similarity Index (Gaussian sliding window) | **250–500 ms** per full 1080p frame | Luminance, contrast, and structural comparison. | **Prohibitive**. Excess CPU sliding-window convolution overhead on 16GB CPU-only machines. |

### 2. Signal-to-Scenario Mapping

- **Renamed Button** (e.g. "New repo" $\to$ "Create repository"):
  - **ARIA Diff:** **Optimal signal**. Instantly detects `role: button, name: "Create repository"` in the accessibility tree. Token normalization and domain synonym mapping resolve the change with zero false positives.
  - **Visual Diff:** Flags a bounding box pixel delta, but cannot determine whether text, font, or icon changed.
- **Moved Menu / Relocated Element** (e.g. Header to sidebar):
  - **ARIA Diff:** Confirms the element still exists in the accessibility tree under a different semantic region/landmark.
  - **Bounding Box Check:** Instantly measures the coordinate delta [x, y, w, h] without raster image comparison overhead.
- **New Dialog / Modal Interstitial** (e.g. "Confirm your email", 2FA barrier):
  - **ARIA Diff:** **Instant detection**. Catches newly rendered `role: dialog` or `role: alertdialog` immediately.
  - **Visual Diff:** Shows the background dimmed by a semi-transparent backdrop overlay, but cannot extract dialog semantics or dismissibility.

## Recommendation

Adopt a **Three-Tier Signal Hierarchy**:
1. **Primary (Semantic Truth):** ARIA snapshot comparison via Playwright `locator.ariaSnapshot()`. It eliminates layout noise, CSS framework rebuilds, and provides true semantic assertions.
2. **Secondary (Spatial Verification):** Bounding box centroid distance check ($\Delta d \le 30\text{px}$) to distinguish stationary elements from relocated elements.
3. **Tertiary (Visual Fallback):** Scoped element-level `pixelmatch` (only when visual assertion is required, e.g., icon-only buttons or canvas components). Never run full-page SSIM on our reference machine.

## Open questions
- None. Benchmarks and integration tests prove the ARIA-first hierarchy runs in sub-100ms per step on CPU.

## Links
- Playwright Aria Snapshots: https://playwright.dev/docs/aria-snapshots
- Pixelmatch repository: https://github.com/mapbox/pixelmatch
