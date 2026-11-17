# Remotion Licensing: Terms, Free Tier, and Applicability to Krama

- **Phase:** 5 (Video export)
- **Researched by:** Nachiketha (research and license analysis, 2026-11-17)
- **Question(s):** Remotion license: check the current terms. Remotion is free only for individuals and small companies; confirm what applies to us.

---

## Findings

### 1. License Model: Team Headcount vs Revenue
- Remotion uses a custom commercial/source-available licensing model: **Remotion License (Free Tier)** vs **Remotion Company License** [verified: remotion.dev/docs/license].
- Crucially, Remotion does **not** enforce a revenue threshold (e.g. no cap at $100k or $1M ARR) [verified: remotion.dev/docs/license].
- The boundary between free and paid commercial use is determined strictly by **organizational headcount / team size**:
  - **Individuals:** Solo developers, creators, freelancers, and hobbyists can use Remotion completely free for both personal and commercial projects [verified: remotion.dev/docs/license].
  - **Small Teams / Organizations (up to 3 employees/members):** For-profit companies or teams with **3 or fewer people** qualify for the free license, with full commercial rights [verified: remotion.dev/docs/license].
  - **Non-Profits & Educational Projects:** Non-profit and educational/research organizations of any size can use Remotion free of charge [verified: remotion.dev/docs/license].
  - **Evaluators:** Anyone evaluating Remotion during proof-of-concept stages is covered under the free tier [verified: remotion.dev/docs/license].

### 2. Feature Parity
- The free license is **100% feature-complete**: there are no watermarks, no resolution restrictions, no frame rate limits, and no artificial pauses [verified: remotion.dev/docs/license].
- Full access to `@remotion/renderer`, `@remotion/player`, `@remotion/cli`, and Remotion composition primitives is included under the free tier.

### 3. Applicability to Krama
- Krama is currently developed by **two students** (Vishwas and Nachiketha) as an open-source educational project.
- With a team size of 2 (≤ 3 headcount), Krama qualifies directly under the **Remotion Free License** with zero licensing cost or royalties [verified].
- No license key, account registration, or payment method is required to install and run Remotion packages via `pnpm` or build CI exports.

### 4. Paid Company License Triggers for Future Deployers
- If an organization adopting or embedding Krama has **4 or more employees/contractors**, they must purchase a **Remotion Company License**:
  - **Remotion for Automators:** Designed for programmatic, server-side, or headless video generation workflows (such as Krama's backend arq export jobs). Current pricing is **$0.01 per render with a $100/month minimum** [verified: remotion.dev/pricing].
  - **Remotion for Creators:** $25/month per seat for manual/creative development seats.
- We must clearly document this in Krama's documentation so enterprise users deploying Krama at scale are aware of their compliance obligations if their organization exceeds 3 people.

---

## Recommendation

1. **Adopt Remotion for Phase 5:** Remotion fully covers Krama's needs without legal or financial impediment under the Remotion Free License.
2. **Explicit Dependency Isolation:** Package Remotion inside `packages/video-exporter` with its own `package.json` (pnpm workspace) so it does not bloat the frontend Next.js client bundles or backend Python environment.
3. **Document Compliance Note:** Add a note in `docs/` and `README.md` clarifying that self-hosted Krama instances with teams of ≤3 people use Remotion freely, while larger commercial organizations require an Automators license from Remotion.

---

## Open Questions
- None. Remotion's license terms are definitive and allow full commercial and non-commercial use for teams of ≤3 people.

---

## Links
- Remotion License Terms: https://www.remotion.dev/docs/license
- Remotion Pricing: https://www.remotion.dev/pricing
