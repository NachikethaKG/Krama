# Phase 6 Decisions & Alignment: do it for me, human takeover, search, languages

- **Phase:** 6 (Do it for me #129, Human takeover #131, Workflow search #135, Multiple languages #132)
- **Document type:** Decision record + research summary (for Nachiketha to read; for both agents to build on)
- **Decided by:** Vishwas, 2026-11-19. Nachiketha is away, so Vishwas also took the decisions in Nachiketha's areas
  (`frontend/`, `packages/`, `policy/`, `export/`); they are marked **[N]** below. Nachiketha: if you disagree with
  one, raise it on the issue it applies to.
- **Written by:** Claude Code on Vishwas's laptop (research #398).
- **References:**
  - [`phase-6-vishwas-do-it-for-me.md`](phase-6-vishwas-do-it-for-me.md) (#129)
  - [`phase-6-vishwas-human-takeover.md`](phase-6-vishwas-human-takeover.md) (#131), spike in
    `assets/phase-6-vishwas-takeover/`
  - [`phase-6-nachiketha-workflow-search.md`](phase-6-nachiketha-workflow-search.md) (#135), spike in
    `assets/phase-6-search/`
  - [`phase-6-nachiketha-multiple-languages.md`](phase-6-nachiketha-multiple-languages.md) (#132), checks in
    `assets/phase-6-languages/`
  - Phase file: [`docs/phases/phase-6-assist.md`](../phases/phase-6-assist.md)

**Scope.** Phase 6 builds #129 → #131 → #135 → #132, in that order, and ships as **v1.3**. The browser extension
(#130), RBAC/teams/audit log (#133) and the public API (#134) stay in the backlog. Desktop and mobile apps (#136) were
closed as a separate product.

---

## 1. Research in five minutes

**Do it for me.** Reverify (#77) already replays stored steps as an approved plan through the normal executor, and
every step already passes the policy; a high-risk step pauses even when the policy allows it. Two things must change
for a user's run: reverify **resets the target first** (for Gitea that deletes what the workflow creates), and it
**fails instead of pausing**. A typed value reappears in up to 6 places in later steps (fill value, `field_values`,
`url_matches` regex, `title_contains`, a heading name, step text), so a new value must be substituted everywhere.
There is **one login session per site** (the test account); no per-user store exists.

**Takeover.** A paused run keeps its browser open for 30 min, so takeover can use the live page. Playwright 1.63's
`page.screencast` works headless on Windows: a still page sends 0 frames, a 1280×800 JPEG q60 frame is 16–115 KB,
the screencast adds 30–65 MB RAM to a ~200 MB browser, and key-to-screen latency over a WebSocket was p50 51 ms /
p95 64 ms. Clicks, keys and Unicode paste reached the DOM. Login walls and CAPTCHAs **stop** the run today (policy
`stop`), so takeover there needs a policy change and new AGENTS.md §4 wording. noVNC needs Linux; a headed browser
only works when the server is the user's laptop.

**Search.** `postgres:16-alpine` has `pg_trgm` and `unaccent`, not pgvector. On 1,032 workflows: full-text alone
found the right workflow in the top 3 for 8/12 queries (0.5 ms); full-text + trigram 11/12 (3.8 ms); all-words, then
any-word, + trigram + a small synonym map 12/12 (5.3 ms median, 78 ms worst; optimistic, the synonyms were written
for the test queries). Same at 20,000 workflows. `GET /workflows` has no text filter and ignores the `status` the
frontend sends.

**Languages.** next-intl 4.15 (MIT) supports Next 16 + React 19 with a cookie locale. Gemini translation with
quoted labels swapped for `[[Qn]]` tokens kept every label byte for byte in **68/68** texts (hi, kn, de, es), but
Gemini was slow and flaky (3 requests and 31–66 s per batch), so translation must be a cached background job.
**No Hindi or Kannada Piper voice passes D1** (Phase 5: no lessac-derived, non-commercial or research-only voices);
German, Spanish and French have clean voices. Piper word timings worked for German, Marathi and Telugu voices.

---

## 2. Decisions

### 2.1 Do it for me (#129)

| # | Decision | Applies to |
|---|---|---|
| P1 | **New run kind `do_it`** on the same executor (not reverify with a flag, not a task run). | #399, #401 |
| P2 | **Eligible:** status `verified`, no sensitive step, nothing pending review. High-risk steps are allowed and pause at the step. | #400, #401 |
| P3 | **Inputs = every non-sensitive single-line `fill`**, grouped by equal value, labelled with the `instructions.py` noun, the recorded value shown as the example (placeholder, not default). Planner-marked inputs maybe later. | #399, #400 |
| P4 | **Substitute the value everywhere it reappears:** fill/select values, navigate paths, `url_matches` (`re.escape`), `title_contains`, `field_values`, visible/absent/checked names, later target names, `instruction_text`. | #400 |
| P5 | **Refuse (`input_unsafe`)** values shorter than 3, outside the example's character class, or when the old value sits in a field we don't substitute. | #400 |
| P6 | **[N] Confirmations:** a preview with the user's values marks the steps that will pause; "Run" = plan approval; every high-risk or policy-flagged step pauses in the live view. No blanket yes up front (AGENTS.md §4). | #401, #402 |
| P7 | **[N] Failure:** stop at the first failed step after the existing one retry; show done / not-run steps; offer "Plan it fresh"; "Finish by hand" once takeover exists. No replan, no whole-run retry. | #401, #402 |
| P8 | **Never reset the target** in a do-it run. | #401 |
| P9 | **Nothing stored on the workflow;** the run is the record. A failure asks validation to re-check the workflow. | #401 |
| P10 | **LLM:** only the policy classifier may call Gemini. No vision verifier/locator, no heal chooser, no replan, no task check. A normal do-it run makes zero LLM calls. | #401 |
| P11 | **[N] Account:** v1 acts in the account Krama is signed in to on that site (test account / Gitea demo user), and the UI says so. Per-user site sessions are their own L task with an ADR, later in Phase 6 and not part of the gate. | #402, #403, #404 |
| P12 | **Steps that type a secret are refused** in v1 (a run-time secret would be stored in `plans.steps`). | #400 |
| P13 | **Owner only** (404 otherwise). | #399, #401 |
| P14 | Keep a do-it run's step screenshots; don't keep its rrweb recording (it shows the user's own data). | #401 |
| P15 | Dropdowns (`select`) are not inputs in v1; they replay the recorded option. | #400 |
| P16 | Self-heal is off during a do-it run (it would act on a guessed element in a real account). | #401 |

### 2.2 Human takeover (#131)

| # | Decision | Applies to |
|---|---|---|
| T1 | **Playwright `page.screencast`** (raw CDP session as fallback). Not noVNC, not a headed local browser, not the DevTools frontend. | #407 |
| T2 | **[N] WebSocket straight to `:8000`:** binary JPEG frames out, JSON input in. Run events stay on SSE. | #406, #408, #411 |
| T3 | **WebSocket auth:** session cookie + `Origin` in `CORS_ORIGINS` + run owner; one controller at a time (CSRF middleware doesn't cover WebSockets). | #406, #408 |
| T4 | **JPEG q60, 1280×800 (1:1 click coordinates), at most 15 fps.** | #407, #411 |
| T5 | **[N] Takeover is offered for** `auth_wall`, `captcha` (after T11), `recovery_exhausted`, `verification_unclear` and failed do-it steps. Never for `rate_limited`, reverify or validation runs. The policy pauses on login walls and CAPTCHA instead of stopping when takeover is possible. | #408, #410 |
| T6 | **Run status stays `paused`** during takeover; `Run.takeover` + `takeover.started/ended` events (additive). | #406 |
| T7 | **[N] Hand-back:** the user says what they did. *Cleared a barrier* → re-check and retry the step; *did this step* → verify its expected state without acting; *did the rest* → final task check. Not verified → pause again. | #409, #411 |
| T8 | **[N] Human-done steps are stored** with `performed_by: human`, capped confidence, and the tutorial shows them as "do it yourself" steps. | #406, #409, #412 |
| T9 | **5 min without input ends the takeover** (run stays paused); the 30 min pause timeout stays the outer limit. | #407 |
| T10 | **Navigation during takeover:** target origin + configured sign-in domains only; `file:`, `chrome:` and private IPs other than the target are blocked (otherwise the server's browser is an SSRF hole once deployed). | #407 |
| T11 | **The run's owner may solve a login wall or CAPTCHA live in Krama's browser.** Never a solver service, a third party or automated bypass. Needs an ADR and new AGENTS.md §4 wording. | #405, #410 |
| T12 | **Frames are memory-only:** never stored, logged or sent to the LLM. The rrweb recording marks the takeover. | #407 |
| T13 | **In-process first;** a Redis pub/sub relay for `RUN_EXECUTOR=arq` is its own Phase 6 task. | #413 |

### 2.3 Workflow search (#135)

| # | Decision | Applies to |
|---|---|---|
| S1 | **Postgres full-text + `pg_trgm` + a small synonym map.** No pgvector, Meilisearch or other new service. | #416, #418 |
| S2 | **Copy columns on `workflows`:** `search_steps`, `search_request`, a generated weighted tsvector + GIN, a trigram index on the title; updated wherever `current_version_id` changes. | #416, #417 |
| S3 | **Per-row `lang regconfig`, default `english`.** Never `simple` with any-word queries (stop words match every row). | #416 |
| S4 | **Query:** all words first, then any word, plus trigram and synonyms. No spell-fix table. | #418 |
| S5 | **score = text × status × freshness:** status verified 1.0, auto-updated 0.95, outdated 0.6, failed 0.3; freshness 0.8 + 0.2·e^(−days since last validation / 30). | #418 |
| S6 | **`?q=` and a working `?status=` on `GET /workflows`** (no new `/search`); offset paging when `q` is set. | #415, #418 |
| S7 | **Contract (additive):** `WorkflowSummary.match {step_seq, snippet}`, `score`, `last_validated_at`. | #415 |
| S8 | **[N] Frontend:** server search, debounced, snippet under the title, status pills send `?status=`. | #419 |
| S9 | Embeddings later, behind the same endpoint, with an ADR. | — |
| S10 | Search the original language only, until languages (#132) decide otherwise. | #416 |

### 2.4 Multiple languages (#132)

| # | Decision | Applies to |
|---|---|---|
| L1 | **[N] next-intl 4.x** (MIT). | #423, #424 |
| L2 | **[N] UI locale from a cookie + Accept-Language;** no `[locale]` URL segment, no route moves. | #423 |
| L3 | **[N] UI: English + Hindi first, then Kannada. Tutorials: Hindi, Kannada, German, Spanish, French.** The UI language and the tutorial language are separate choices. | #425, #426, #427 |
| L4 | **Gemini, one batch per tutorial,** quoted labels (and, for older texts, the step's target name) swapped for `[[Qn]]` tokens and checked byte for byte; a failed check is an error, never a half-translated text. Reviewed per-language templates may replace the LLM later. | #420, #422 |
| L5 | **Lazy:** translated per (workflow version, language) in an arq job on first request; cached by (sha256 text, language, prompt version). | #422 |
| L6 | **[N] UI labels always stay in the site's own language,** byte for byte; quote marks per language. | #422, #427 |
| L7 | **Narration only with a D1-clean voice:** German `thorsten` (CC0), Spanish `davefx` (CC0), French `siwis` (CC BY 4.0, credit). **Hindi and Kannada: translated captions, no narration.** | #420, #428 |
| L8 | A time-boxed spike on **Indic Parler-TTS** (Apache-2.0) CPU speed and RAM; adopt only if it fits a 16 GB CPU-only laptop. | #430 |
| L9 | **[N] Bundled Noto Sans Devanagari / Kannada** (OFL) in the video exporter via `@remotion/fonts`. | #429 |
| L10 | **Contract (additive):** a `Translation` read model; `language` on the export request, `Export` and `TutorialSpec`; a `Translator` port. ADR for translation + per-language voices (updates ADR 0004). | #420, #421 |
| L11 | Tests use FakeProvider fixtures from the research replies; real Gemini only at checkpoints. | #422 |

### 2.5 Process

- **One contract PR per feature,** opened at the start of its milestone (do it for me first). All are additive minor
  bumps.
- All task issues exist from the start, in milestones 6.1–6.4. The idea issues #129, #131, #135 and #132 are
  tracking issues, closed by the exit gate #431.
- In Nachiketha's areas: commit with `KRAMA_CROSS_EDIT=1`, label the PR `cross-boundary`.

---

## 3. Exit gate (v1.3)

On a 16 GB CPU-only laptop, free tiers only; CI uses fakes, real Gemini only here (#431).

- **Do it for me:** ≥ 8/10 Gitea replays with **new** values succeed (checked independently via the Gitea API); every
  destructive step pauses for confirmation; no secrets in artifacts; one GitHub checkpoint run.
- **Takeover:** a run paused at a Gitea login wall is finished by hand in the UI, resumes and completes; the human-done
  step shows as "do it yourself"; the screencast adds ≤ 300 MB RAM.
- **Search:** the right workflow in the top 3 for ≥ 10/12 **held-out** queries (not the spike's); outdated ranked below
  verified; p95 < 100 ms at 1,000 workflows.
- **Languages:** UI in English + Hindi; one tutorial played in Hindi (captions) and exported in German (narrated), with
  every quoted UI label unchanged.

---

## 4. Still open

- **"My account"** waits for per-user site sessions (#403, #404); v1 acts in the test account.
- Whether a CAPTCHA solved by a human actually clears in headless Chromium is untested.
- The takeover CPU numbers are from Vishwas's laptop (i5-14450HX); Nachiketha's laptop is still to measure.
- GitHub's renaming of new repository names (spaces, Unicode) is unverified; P5's character-class rule guards it.
- Hindi and Kannada UI and tutorial text need a native reader. Whether CC BY-SA training data makes a voice's audio
  share-alike is a legal question (it only matters for the Marathi/Bengali voices, which we don't use).
- The German voice reads English labels with German pronunciation ("Create"); accepted for now.
