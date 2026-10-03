# Phase 4: Reliability (UI drift)

**Goal:** tutorials stay correct as websites change. Stored workflows are re-checked on a schedule; drift is detected; the agent tries to self-heal; otherwise the tutorial is marked **OUTDATED** for human review. Every change creates a new workflow version.

**Release tag:** `v1.1`

**Who builds what**
- **Vishwas:** self-healing (re-locating elements and re-verifying), workflow versioning in the DB and API.
- **Nachiketha:** `validation/`: scheduled validation runs, drift detection and classification, plus the version and review UI.

---

## Research before starting

**Vishwas**
- **Self-healing locators:** how does Healenium score candidate elements when a locator breaks (attribute similarity, position, text)? When is LLM re-grounding (screenshot + ARIA) better? How do you avoid "healing" onto the wrong element?
- **Versioning:** how do you store workflow versions (copy-on-write rows vs a JSON diff)? What counts as a new version vs the same one?
- **Semantic step diff:** how do you compare two versions step by step so the UI can show what changed?

**Nachiketha**
- **Drift detection signals:** accessibility-tree diff vs DOM diff vs visual diff. Look at `pixelmatch` and SSIM; they must be CPU-friendly. Which signal catches a renamed button, a moved menu, a new dialog?
- **Classifying drift:** cosmetic change (ignore) vs moved element (heal) vs changed flow (outdated). Where is the line?
- **Scheduling:** arq cron jobs. How often to validate without hitting rate limits? Back-off for sites that fail.
- **How docs tools handle staleness:** how do Scribe, Tango and other documentation tools flag outdated content? What does a good review queue look like?

**Together**
- Agree on the rules: what triggers auto-heal vs OUTDATED vs human review, and who gets notified.

---

## Sprint 4.1: detect

| Vishwas | Nachiketha |
|---|---|
| `db/` + `api/`: `workflow_versions`, `validations` tables, `GET /workflows/{id}/versions` | `validation/`: scheduled re-runs of stored workflows (arq cron) through the `Validator` port |
| `agent/`: expose locator-miss and state-mismatch details for validation | `validation/`: drift detection (ARIA diff, visual diff, expected-state mismatch) and classification |

## Sprint 4.2: heal and review

| Vishwas | Nachiketha |
|---|---|
| `agent/`: self-healing: re-locate via the fallback chain, re-verify, save as a new version | Frontend: VALIDATED / OUTDATED badges, version history and step-by-step diff view |
| `runs/`: "regenerate" flow for workflows that can't heal | Frontend: review queue for tutorials that failed self-healing; "regenerate" action |

## Exit criteria
- A deliberately modified Gitea template (renamed button) is detected, self-healed, and saved as a new tutorial version.
- A deliberately broken flow (removed page) ends up OUTDATED in the review queue.
- Validation runs on Nachiketha's laptop without slowing normal use (one browser at a time).
