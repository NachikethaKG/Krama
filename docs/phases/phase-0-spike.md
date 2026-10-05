# Phase 0: Technical spike

**Goal:** answer the PRD's biggest risk: *can an agent reliably perform one task on one website?* Target: "create a repository" in local Gitea.

**Release tag:** `v0.0-spike`

**Who builds what**
- **Vishwas:** browser execution (`agent/`), LLM layer (`llm/`), first planner and rule-based verifier.
- **Nachiketha:** what the agent *sees and records* (`observer/`), how we *measure* it (`benchmarks/`), and the first UI screens on fixtures.

---

## Research before starting

> **Research chat prompts:** copy yours from [#25 (Vishwas)](https://github.com/NachikethaKG/Krama/issues/25) or [#26 (Nachiketha)](https://github.com/NachikethaKG/Krama/issues/26), or run `just research-prompt 0 <name>`. Together questions: [#27](https://github.com/NachikethaKG/Krama/issues/27). How it works: [`docs/research/`](../research/README.md).

**Vishwas**
- **Playwright for Python:** role-based locators (`get_by_role`, `get_by_label`), auto-waiting, `expect` assertions. What does `locator.aria_snapshot()` return, and how big is it on a Gitea page?
- **Existing browser agents:** how do **browser-use** and **Stagehand** represent the page to the LLM (DOM, ARIA, screenshots) and its actions (click/fill/…)? Which runs from Python? Is either worth adopting, or do we copy ideas into our own thin layer? (This becomes ADR 0002.)
- **Gemini API:** the `google-genai` SDK and **structured output** (`response_schema` / JSON mode) to get a plan as valid JSON. What are the free-tier limits (requests per minute and per day) for the Flash model? How do you handle `429` errors?
- **Planning prompts:** how do agents prompt for step plans with expected outcomes? Look at the browser-use system prompt and the WebArena / SeeAct papers (skim).

**Nachiketha**
- **rrweb recording:** `rrweb.record({ emit })` options. Inject it into every page with Playwright's `add_init_script` and get the events back into Python with `expose_binding`. Does it survive page navigations? How big is a recording of a 1-minute task?
- **Page state capture in Playwright:** `page.screenshot` (full page vs viewport), `page.on("request"/"response")` for a network summary, and how to keep the capture fast (it runs after every action).
- **rrweb replay:** `rrweb-player` / `Replayer` API. How do you position an SVG overlay (cursor, highlight) on top of the replay iframe when the player is scaled?
- **Benchmarking agents:** how do WebArena / Mind2Web define task success? What should our harness record per run (success, steps, retries, time, LLM calls)?
- **Next.js 16 App Router:** read `frontend/node_modules/next/dist/docs/` (version 16 changed a lot). Also: client vs server components, and where `fetch` and `EventSource` should live.

**Together**
- Both create a Gemini API key (one each; limits are per key) and run one structured-output call from Python to confirm quota.
- Agree on the definition of "reliably" for the exit gate (proposed: ≥ 8 of 10 runs).

---

## Sprint 0.1: execute and observe

| Vishwas | Nachiketha |
|---|---|
| `agent/`: Playwright session (headless), action executor for click / fill / select / navigate / press / wait | `observer/`: implements the `Observer` port: URL, ARIA snapshot, screenshot and network summary after each action |
| Hand-written "create repo in Gitea" script using the executor | `observer/`: rrweb injection + event collection per run, saved as JSON |
| ADR 0002: raw Playwright vs Stagehand vs browser-use | Tests for the observer against local Gitea |
| JSON run log (actions, timings) | Frontend: **Plan Review UI** on fixtures (task input, step list, risk badge, Edit / Approve / Reject) |

## Sprint 0.2: plan and measure

| Vishwas | Nachiketha |
|---|---|
| `llm/`: `LLMProvider` with `GeminiProvider` + `FakeProvider` (optional `OllamaProvider`) | `benchmarks/harness`: run a task N times and report success rate, steps, retries, duration, LLM calls |
| `planner/`: task → steps with `expected_state` (structured output) | `benchmarks/tasks/gitea-create-repo.yaml` (shared file format) |
| `verifier/`: rule-based URL + ARIA assertions | Frontend: rrweb replay + SVG overlay spike (cursor and highlight follow a step's bbox) |
| CLI: `uv run krama run "create a repo"` | Frontend: **Live Run view** consuming the mock SSE stream |

## Exit criteria
- The CLI runs a **planned** (not hardcoded) Gitea repo creation ≥ 8/10 times on Nachiketha's laptop with Gemini, measured by the benchmark harness.
- Every run produces observer captures and an rrweb recording.
- The rrweb replay + overlay demo works in the browser.
- ADR 0002 merged.
