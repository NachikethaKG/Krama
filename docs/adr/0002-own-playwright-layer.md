# 0002 — Our own thin layer on Playwright, not browser-use or Stagehand

- **Status:** accepted
- **Deciders:** Vishwas (research and decision), Nachiketha (review)
- **Issue:** #30 · Research: [`phase-0-vishwas-browser-agents.md`](../research/phase-0-vishwas-browser-agents.md) (#25)

## Context
The agent has to drive a real website in headless Chromium. Two open-source libraries already do "LLM drives a browser": **browser-use** and **Stagehand**. Before building `backend/app/agent/`, we checked whether adopting one of them would save work.

Krama's core flow constrains the choice:
1. The **whole plan** is made up front and approved by a human **before** execution.
2. Every step is checked **mechanically** against its `expected_state` by our verifier.
3. Destructive actions pause at the policy layer.
4. CAPTCHAs and bot walls **stop** the run.
5. Everything runs on a 16 GB CPU-only laptop within the Gemini free tier (5 requests/min, 20/day per model).

Both libraries were installed and each ran a live "create a repository" task on local Gitea with `gemini-2.5-flash` (2026-10-07):

| | Our own thin layer on Playwright | browser-use 0.13.11 | Stagehand 4.1.0 |
|---|---|---|---|
| Python support | native; Playwright 1.63 already pinned | native, 106 packages / 227 MB | thin Python client; the logic is a 2 MB minified JS bundle |
| Page representation | ARIA snapshot YAML (~120–1,400 tokens per Gitea page), our choice | indexed DOM + accessibility list + screenshot (on by default) | DOM + accessibility hybrid; the LLM picks a node id → **absolute XPath** |
| Reliability | deterministic per step: role locators, `expect`, our verifier | 1/1 success; autonomous loop judges its own success; 1 browser-launch hang in 3 | 1/1 success; absolute XPaths are fragile; its cache was disabled locally |
| CPU / LLM cost per task | Chromium only; **1 planning call (~1.5k tokens)** | ~970 MB RAM; **5 calls, ~35k tokens** | 1 call per action; **~7k tokens** for 3 actions |
| Lock-in | none | high: its own loop, prompts and policy | medium-high: opaque bundle, Browserbase SDK |
| Conflicts with our rules | — | its system prompt says "CAPTCHAs are solved automatically" and to try other sites when blocked | — |

## Decision
**We build our own thin layer on raw Playwright for Python** (`backend/app/agent/`). It executes the approved plan step by step; the LLM is used only for planning (and, from Phase 1, for re-grounding a step whose target doesn't resolve).

- Elements are located by ARIA **role + accessible name** (substring match), with a CSS selector as fallback (`Target` in the contract). First version: #28.
- Success of a step is decided by **our verifier**, never by the LLM's opinion.

We **copy these ideas** from the two libraries:
1. A compact, **numbered list of interactive elements** built from the ARIA snapshot, for re-grounding a step (Phase 1; the best grounding method in the SeeAct paper).
2. browser-use's **"new since the last step" marker**, to point the LLM at what changed.
3. Stagehand's **observe / act split**: find candidates first, then act on one.
4. A **cache of resolved targets** per step, with self-healing when a cached target stops matching (Phase 4). We store role + name, never absolute XPaths.
5. Wait for the DOM to settle after an action, never for `networkidle`.

## Alternatives considered
- **Adopt browser-use.** Rejected:
  - Its autonomous loop plans and acts on its own, which contradicts plan → approve → execute.
  - It judges success itself, and its prompt contradicts our CAPTCHA and access rules.
  - About 20× the tokens of our design per task, which doesn't fit the free tier.
- **Adopt Stagehand.** Rejected:
  - Its `act` per step fits better, but its logic is an opaque JS bundle we can't debug or patch from Python.
  - It targets absolute XPaths, and its caching needs Browserbase's service.
- **Wrap one of them behind an interface and decide later.** Rejected: both own the browser session and the page representation, so a thin wrapper would still inherit their loop and dependencies.

## Consequences
- We write and maintain locator fallback, re-grounding and self-healing ourselves (Phases 1 and 4). The ideas above keep that work small.
- No new dependencies: Playwright is already pinned. `architecture.md` already says "Playwright Python" for the browser worker, so it doesn't change.
- Token use per task stays small enough for the free tier (one planning call per run in Phase 0).
- Revisit if Phase 3 (real GitHub, larger pages that change often) shows our locator chain is much less robust than these libraries.
