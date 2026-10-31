# Summary: Phase 4 Research (Nachiketha)

- **Phase:** 4
- **Researched by:** Nachiketha
- **Issue:** [#106](https://github.com/NachikethaKG/Krama/issues/106)
- **Date:** 2026-10-31

---

## Decisions Made

1. **Signal Priority Hierarchy:**
   - Primary: ARIA snapshot comparison via Playwright `locator.ariaSnapshot()`.
   - Secondary: Target element bounding box centroid shift ($\Delta d \le 30\text{px}$).
   - Tertiary: Scoped element-level `pixelmatch` for raster assertion.
   - Strictly avoid full-page SSIM on 16GB CPU-only machines.

2. **Three-Tier Drift Boundaries:**
   - `CLASS_1_COSMETIC`: $\Delta d \le 30\text{px}$, selector valid $\to$ Status `VALIDATED`, no version bump.
   - `CLASS_2_MOVED` / `CLASS_2_REFACTORED`: ARIA similarity $\ge 0.85$, post-condition passes $\to$ Status `HEALED`, auto-bump `v1.0` $\to$ `v1.1`.
   - `CLASS_3_OUTDATED`: Element missing or blocking modal dialog $\to$ Status `OUTDATED`, halt execution, send to Review Queue.

3. **Concurrency and Scheduling:**
   - Enforce `max_jobs = 1` for the ARQ validation queue to guarantee safety on 16GB RAM.
   - Enforce 60-second domain cooldown and 10 runs/day on `github.com`.
   - Implement exponential back-off ($1\text{h} \to 4\text{h} \to 24\text{h} \to 7\text{d}$) and a 3-strike 24-hour circuit breaker.

4. **Staleness Handling:**
   - Differentiate Krama from passive tools (Scribe/Tango) through proactive background verification.
   - Implement `/dashboard/reviews` with side-by-side expected vs observed step diffs.

---

## Decisions that need Vishwas / the team

- Align on the shared domain synonym mapping dictionary in `contracts/` so both backend locator healing and frontend step diffs use identical semantic rules.
- Review and verify the Review Queue API payload schema against `GET /workflows/{id}/versions`.

---

## Changes Suggested to Phase File

- No breaking changes needed to [`docs/phases/phase-4-reliability.md`](../phases/phase-4-reliability.md). Sprint 4.1 and Sprint 4.2 task ownership align cleanly with these findings.

---

## Parking Lot

- Future multi-modal vision fallback (Gemini Vision) for canvas or WebGL components when ARIA tree does not expose semantic accessibility nodes.
