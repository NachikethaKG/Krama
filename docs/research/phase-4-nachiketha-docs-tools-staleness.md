# How documentation tools handle staleness: Scribe, Tango, and Review Queue design

- **Phase:** 4
- **Researched by:** Nachiketha (research on industry documentation tools, 2026-10-31; decisions by Nachiketha)
- **Question(s):** **How docs tools handle staleness:** how do Scribe, Tango and other documentation tools flag outdated content? What does a good review queue look like?

## Findings

### 1. Industry SOTA Analysis

| Tool | Staleness Detection Mechanism | Remediation Model | Limitations |
| :--- | :--- | :--- | :--- |
| **Scribe** | - **Passive User Feedback:** Viewers click a "Flag as outdated" button on viewed SOP documents.<br>- **Inactivity Timer:** Automatically flags documents that have not been viewed or edited in >180 days. | Author must manually re-record the broken SOP steps from scratch. | **Zero automated verification**. A broken step remains live and misleading until an end-user encounters the failure and complains. |
| **Tango** | - **Extension Telemetry:** Detects broken elements only when authors or users re-execute/edit workflows via the browser extension.<br>- Tracks anchor invalidation during re-captures. | Author manually recaptures single screenshots and updates steps. | No continuous background headless testing. Staleness is discovered reactively. |
| **Krama** | - **Proactive Autonomous Headless Verification:** Scheduled background execution against real web applications (Playwright + ARQ).<br>- Detects semantic drift, relocations, and flow breaks before users ever see them. | - **Auto-Healing:** Minor drifts automatically self-heal to `v1.1`.<br>- **Review Queue:** Breaking flows route to author with side-by-side diffs. | Requires isolated test environments/accounts for state-mutating workflows. |

### 2. Review Queue UX Architecture (`/dashboard/reviews`)

The Review Queue gives authors full visibility into automated verification outcomes:
- **Review Queue Table:**
  - Columns: Workflow Title, Target Domain, Status Badge (`VALIDATED`, `HEALED`, `OUTDATED`), Failed Step Index, Last Validated Timestamp, Actions.
- **Side-by-Side Step Diff View:**
  - **Left Column (Expected State - Recorded v1.0):** Screenshot with highlighted target bounding box, recorded selector, and caption.
  - **Right Column (Observed State - Live Verification):** Live screenshot with observed bounding box, ARIA snapshot diff, and engine reason.
- **Author Action Bar:**
  - `[✓ Approve Auto-Heal (v1.1)]`: Accepts suggested selector mutation and publishes updated tutorial.
  - `[↻ Regenerate Workflow]`: Triggers a new automated agent run from current application state.
  - `[✕ Dismiss]`: Acknowledges notification without changing tutorial state.

## Recommendation

1. Implement Next.js `/dashboard/reviews` route providing the side-by-side expected vs observed inspector.
2. Store `workflow_review_items` in PostgreSQL with links to screenshot artifacts and ARIA snapshots.
3. Automatically promote high-confidence Class 2 heals to `v1.1`, while routing Class 3 breaking changes directly to the Review Queue.

## Open questions
- None. The schema maps cleanly to the tables created in migration `e97aef1f9b9c_workflow_versions_and_validations.py`.

## Links
- Scribe Help Center (Doc verification & feedback): https://help.scribehow.com/
- Tango Documentation: https://www.tango.us/
