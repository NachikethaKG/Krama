# Classifying drift: cosmetic change (ignore) vs moved element (heal) vs changed flow (outdated)

- **Phase:** 4
- **Researched by:** Nachiketha (research and validation tests run on Nachiketha's reference machine: Windows 11, 16GB RAM, CPU-only, 2026-10-31; decisions by Nachiketha)
- **Question(s):** **Classifying drift:** cosmetic change (ignore) vs moved element (heal) vs changed flow (outdated). Where is the line?

## Findings

Tested against simulated DOM refactors, layout shifts, and Gitea templates. Verified locally with Playwright integration test suite (`tests/test_verifier_engine.py`).

### 1. Boundary Definitions

| Drift Class | Definition & Trigger Conditions | Engine Action | Versioning Impact |
| :--- | :--- | :--- | :--- |
| **Class 1: Cosmetic Change (IGNORE / PASS)** | - Action element locator resolves cleanly; accessible name and role match.<br>- Centroid coordinate delta $\Delta d \le 30\text{px}$ (e.g., subtle padding adjustments, responsive navbar offset).<br>- Styling/color change without semantic disruption. | Pass validation step cleanly. | No version increment needed (workflow remains `v1.0`). No notification noise. |
| **Class 2: Moved or Refactored Element (HEAL)** | - Original selector fails, but element exists in current ARIA tree with high-similarity accessible name (Levenshtein ratio $\ge 0.85$ + domain synonym match).<br>- Element moved to new landmark or coordinate delta $\Delta d > 30\text{px}$.<br>- Fallback locator chain succeeds in re-grounding target.<br>- Expected post-condition verifies successfully (URL or modal changes as planned). | Auto-heal locator to resilient role selector (`role=button[name="..."]`). | Auto-increment minor version (`v1.0` $\to$ `v1.1`). Log audit record for author. |
| **Class 3: Changed Flow / Breaking Drift (OUTDATED)** | - Target element cannot be resolved in ARIA tree or DOM.<br>- Pre-requisite step fails to produce expected state (e.g., page 404, removed form field).<br>- Unexpected blocking dialog requires new interactive branch (e.g., 2FA prompt, email confirmation modal). | Abort execution immediately (fail-fast to conserve CPU/RAM). | Mark workflow status as `OUTDATED`. Enqueue step diff to Review Queue. |

### 2. Centroid Distance Formulation
For expected box $(x_1, y_1, w_1, h_1)$ and observed box $(x_2, y_2, w_2, h_2)$:

$$C_{x} = x + \frac{w}{2}, \quad C_{y} = y + \frac{h}{2}$$

$$\Delta d = \sqrt{(C_{x,2} - C_{x,1})^2 + (C_{y,2} - C_{y,1})^2}$$

A $30\text{px}$ boundary safely accommodates standard UI adjustments (e.g., alert banners pushing content down, minor padding updates) without falsely triggering relocation logic.

### 3. Verification of Post-Condition
Auto-healing is safe only when the post-condition succeeds:
- If a click action occurs on a healed button, the subsequent step or expected URL change must execute without error.
- If the post-condition fails, the step is immediately downgraded to Class 3 (`OUTDATED`) to prevent "healing" onto the wrong element.

## Recommendation

Implement a strict three-tier classification pipeline:
1. `CLASS_1_COSMETIC`: $\Delta d \le 30\text{px}$ and primary selector passes $\to$ status `VALIDATED`.
2. `CLASS_2_MOVED` / `CLASS_2_REFACTORED`: ARIA similarity $\ge 0.85$ and post-condition passes $\to$ status `HEALED`, bump version `v1.0` $\to$ `v1.1`.
3. `CLASS_3_OUTDATED`: Element missing or blocking interstitial $\to$ status `OUTDATED`, halt run, create `ReviewItem`.

## Open questions
- Domain synonym dictionary should be maintained in `contracts/` or shared backend constants so both frontend and backend use identical semantic mappings.

## Links
- Phase 4 decisions alignment: [`phase-4-decisions-alignment.md`](phase-4-decisions-alignment.md)
- Together drift rules: [`phase-4-together-drift-rules.md`](phase-4-together-drift-rules.md)
