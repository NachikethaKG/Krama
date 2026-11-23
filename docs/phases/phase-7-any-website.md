# Phase 7: Krama on any website

**Goal:** a user names any public website and a task; Krama records a verified tutorial of it, or does it in the
user's own account, without hand-written notes about the site.

**Release tag:** `v1.4`

**Who builds what:** Nachiketha is away, so Vishwas builds all of Phase 7, including Nachiketha's areas (frontend,
packages, policy, observer, benchmarks). Those PRs use `KRAMA_CROSS_EDIT=1` and the `cross-boundary` label.

---

## Research (done)

Epic [#455](https://github.com/NachikethaKG/Krama/issues/455). Spike [#457](https://github.com/NachikethaKG/Krama/issues/457):
[phase-7-vishwas-any-website-spike.md](../research/phase-7-vishwas-any-website-spike.md). The opt-in local model for
development: [#456](https://github.com/NachikethaKG/Krama/issues/456), [ADR 0010](../adr/0010-local-llm-as-opt-in-dev-provider.md).

**Decided (2026-11-23):** [`phase-7-decisions-alignment.md`](../research/phase-7-decisions-alignment.md)
(W1–W8, Q1–Q4, A1–A5, K1, U1–U3). In short:
- **Outline, then look before each step:** one call writes an outline the user approves; then observe → decide one
  action → act → verify, repeated, for new tasks on every site. Risky steps still pause.
- **Verify by what changed:** the observed change becomes the step's expected state; one "is it done?" check at the
  end. No replan reviews: limits (20 steps, 25 calls, 3 decisions without progress → pause and offer takeover).
- **The LLM sees the whole page**, trimmed to ~24k characters. Step decisions use their own Gemini model order.
- **Sign in to any site:** sessions per origin, SSO hosts learned during the sign-in takeover, a generic signed-in
  check, sensitive sites refused.
- **Site notes** built by code from earlier verified workflows on the same site.
- The old plan-up-front planner stays behind a setting for v1.4, then goes.

Development runs use `LLM_PROVIDER=ollama` (qwen2.5:7b); real Gemini only at checkpoints and the gate.

---

## Sprint 7.1: Quick fixes

| Issue | Size | Notes |
|---|---|---|
| #461 Show the LLM the whole page, trimmed to a budget | M | observer touch is [N] |
| #462 Open the target URL's own path as the start page | S | |
| #463 URL checks include the query string | S | observer touch is [N] |
| #464 Log every LLM call to the database | S | |

## Sprint 7.2: Look before each step

| Issue | Size | Notes |
|---|---|---|
| #465 ADR: look before each step | S | |
| #466 contract: outline, step mode and decision events | S | contract-change |
| #467 Outline planner | M | |
| #468 Step decider | M | |
| #469 Verify a step by what changed; final done check | M | |
| #470 Executor loop: decide, act, verify, with limits | L | |
| #471 Store the workflow and tutorial from the steps taken | M | |
| #472 Frontend: outline approval and live decisions | M | [N] |

## Sprint 7.3: Sign in to any site

| Issue | Size | Notes |
|---|---|---|
| #473 ADR: sign in to any site | S | updates ADR 0007, AGENTS.md §4 |
| #474 contract: sites by origin and sign-in hosts | S | contract-change |
| #475 Site sessions per origin | M | migration |
| #476 Generic "who is signed in?" check | M | |
| #477 Takeover: allow SSO hosts during sign-in, popups in the same tab | S | |
| #478 Policy: refuse sensitive sites | S | [N] |
| #479 Frontend: any URL and "Sign in to this site" | M | [N] |

## Sprint 7.4: Site notes

| Issue | Size | Notes |
|---|---|---|
| #480 Site notes from verified workflows | M | |

## Sprint 7.5: Real-site benchmark and gate

| Issue | Size | Notes |
|---|---|---|
| #481 Real-site benchmark runner and tasks | M | [N] benchmarks |
| #482 Phase 7 exit gate | M | |

## Exit criteria (#482)

On a 16 GB CPU-only laptop, free tiers only, real Gemini; CI uses fakes.

- [ ] **Real sites:** a held-out set of 12 public sites, 2 tasks each (8 without an account, 4 with the owner's own
  free account): ≥ 18/24 verified with at most one takeover each; every stored tutorial replays once without an LLM
  call.
- [ ] **No regressions:** the Gitea benchmark at or above its v1.3 rate; the Phase 6 checks pass.
- [ ] **Safety:** destructive steps pause; no CAPTCHA solved or bypassed; sensitive sites refused; no secrets or
  account names in artifacts; tutorials universal.
- [ ] **Cost:** median ≤ 10 LLM calls per task; a decision's p50 ≤ 15 s on Gemini; fits the 16 GB laptop with the
  stack, the API and one browser.
