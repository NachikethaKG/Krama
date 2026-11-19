# Phase 6: Do it for me, human takeover, search, languages

**Goal:** Krama does a verified task *for* the user, lets the user take over a run when a human is needed, finds the
right workflow by search, and speaks more than English.

**Release tag:** `v1.3`

**Who builds what:** Nachiketha is away, so Vishwas builds all of Phase 6, including Nachiketha's areas (frontend,
packages, policy, export). Those PRs use `KRAMA_CROSS_EDIT=1` and the `cross-boundary` label, and every decision that
touches his area is marked **[N]** in the decisions note.

The other Phase 6 ideas stay in the backlog: [phase-6-later.md](phase-6-later.md).

---

## Research (done)

Research issue [#398](https://github.com/NachikethaKG/Krama/issues/398). Notes:
[do it for me](../research/phase-6-vishwas-do-it-for-me.md),
[human takeover](../research/phase-6-vishwas-human-takeover.md),
[workflow search](../research/phase-6-nachiketha-workflow-search.md),
[multiple languages](../research/phase-6-nachiketha-multiple-languages.md).

**Decided (2026-11-19):** [`phase-6-decisions-alignment.md`](../research/phase-6-decisions-alignment.md)
(P1–P16, T1–T13, S1–S10, L1–L11). In short:
- **Do it for me:** a new `do_it` run kind replays a verified workflow with the user's own values, never resets the
  site, pauses at every risky step, and makes no LLM calls in normal runs. v1 acts in the account Krama is signed
  in to; per-user site sessions come later in the phase.
- **Takeover:** Playwright screencast over a WebSocket; the owner may sign in or solve a CAPTCHA live (ADR + new
  AGENTS.md §4 wording; never a solver or bypass); human-done steps become "do it yourself" steps.
- **Search:** Postgres full-text + trigram + synonyms on `GET /workflows?q=`, ranked by text × status × freshness.
- **Languages:** next-intl UI (en, hi, then kn); tutorials translated by Gemini with UI labels kept exact (hi, kn, de,
  es, fr); narration only with license-clean voices (de, es, fr), captions only for hi and kn.

Order: contract PR first in each sprint, then code. One issue per branch and PR.

---

## Sprint 6.1: Do it for me (#129)

| Issue | Size | Notes |
|---|---|---|
| #399 contract: `do_it` run kind, workflow inputs, run request | S | contract-change |
| #400 Find a workflow's inputs and substitute the user's values | M | |
| #401 API, executor `do_it` behaviour, run-kind migration | M | |
| #402 Frontend: "Do it for me" button, input form, step preview | M | [N] |
| #403 ADR: per-user site sessions | S | |
| #404 Per-user site sessions (the user's own account) | L | own contract PR; not in the gate |

## Sprint 6.2: Human takeover (#131)

| Issue | Size | Notes |
|---|---|---|
| #405 ADR + AGENTS.md §4: owner may solve a login wall or CAPTCHA live | S | |
| #406 contract: takeover events, `Run.takeover`, `performed_by`, endpoints | S | contract-change |
| #407 Takeover session in the executor: screencast, input, navigation guard | M | |
| #408 Takeover API: start, hand back, screen WebSocket | M | |
| #409 Hand-back: re-check and continue the run | M | |
| #410 Policy: pause for takeover on login walls and CAPTCHA | S | [N] |
| #411 Frontend: takeover viewer in the live run view | L | [N] |
| #412 Tutorial: human-done steps as "do it yourself" | S | [N] |
| #413 Takeover in worker mode: Redis relay | M | |
| #414 End-to-end: finish a Gitea login wall by hand | S | |

## Sprint 6.3: Workflow search (#135)

| Issue | Size | Notes |
|---|---|---|
| #415 contract: workflow search fields | S | contract-change |
| #416 Search columns, indexes and backfill | M | |
| #417 Keep the search text in sync with the current version | S | |
| #418 Search query, ranking and the status filter | M | |
| #419 Frontend: server-side workflow search | M | [N] |

## Sprint 6.4: Multiple languages (#132)

| Issue | Size | Notes |
|---|---|---|
| #420 ADR: translation and per-language voices | S | updates ADR 0004 |
| #421 contract: `Translation`, language fields, `Translator` port | S | contract-change |
| #422 Translator, translations table and translation job | M | |
| #423 Frontend: next-intl setup with cookie locale | S | [N] |
| #424 Frontend: move UI strings into messages | L | [N] |
| #425 UI in Hindi | S | [N] |
| #426 UI in Kannada | S | [N] |
| #427 Player: tutorial language switch | M | [N] |
| #428 Export in a language: translated captions and narration | M | [N] |
| #429 Video exporter: Indic fonts and translated fixed strings | S | [N] |
| #430 Research: Indic Parler-TTS on CPU (time-boxed) | M | |

## Exit criteria (#431)

On a 16 GB CPU-only laptop, free tiers only; CI uses fakes, real Gemini only at the gate.

- [ ] **Do it for me:** ≥ 8/10 Gitea replays with new values succeed (checked via the Gitea API); every destructive
  step pauses; no secrets in artifacts; one GitHub checkpoint run.
- [ ] **Takeover:** a run paused at a Gitea login wall is finished by hand in the UI, resumes and completes; the
  human-done step shows as "do it yourself"; the screencast adds ≤ 300 MB RAM.
- [ ] **Search:** the right workflow in the top 3 for ≥ 10/12 held-out queries; outdated below verified; p95 < 100 ms at
  1,000 workflows.
- [ ] **Languages:** UI in English + Hindi; one tutorial played in Hindi (captions) and exported in German (narrated),
  with every quoted UI label unchanged.
