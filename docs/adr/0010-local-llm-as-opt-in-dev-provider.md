# 0010 — A local LLM (Ollama) as an opt-in development provider

- **Status:** accepted (supersedes decision 1 of [ADR 0003](0003-no-local-model-for-text-jobs.md))
- **Deciders:** Vishwas
- **Issue:** #456 (part of the Phase 7 idea #455)

## Context
Phase 7 (#455) makes Krama work on any website. That means many more LLM calls while it is built: the spike (#457)
and a look-before-each-step agent ask the model once per step, not once per task. The Gemini free tier allows about
20 requests per day per model, so a day of development can use up the quota that real checks and the exit gate need.

ADR 0003 (2026-10) decided not to build an `OllamaProvider`, because a code template wrote instruction text as well as
any model, and the reference laptop (16 GB, no GPU) can't run local models. It kept the `LLMProvider` seam and said a
local provider later needs only a new ADR.

Measured on 2026-11-23 (Vishwas's laptop, RTX 4050 6 GB, Ollama 0.17.1, `qwen2.5:7b`): Ollama's `format` field takes
our Pydantic JSON schemas (with `$defs`) and returned a plan that validated against the planner's schema in 15 s.
A real planning run through `LLM_PROVIDER=ollama` planned, was approved and executed on two public pages.

## Decision
1. **Add `OllamaProvider` behind `LLMProvider`, opt-in only:** `LLM_PROVIDER=ollama`, `OLLAMA_URL`
   (default `http://127.0.0.1:11434`), `OLLAMA_MODEL` (default `qwen2.5:7b`), `OLLAMA_TIMEOUT_S` (180),
   `OLLAMA_NUM_CTX` (8192; Ollama's own default of 4096 tokens silently cuts long planner prompts).
2. **Development only.** Gemini stays the default and the reference for every gate, benchmark and demo; CI and tests
   keep the fake provider. Nothing in the product may need a local model (AGENTS.md rule 10).
3. **Text only.** A call with an image raises `LLMError`. With `LLM_PROVIDER=ollama` the composition roots treat the
   provider like the fake one: no vision verifier or locator, no task check, no heal chooser.
4. **Errors:** not running or no answer in time → `LLMUnavailableError` with a clear message; a model that isn't
   pulled (404) or another error answer → `LLMError`; a reply that doesn't fit the schema → one more try.

Decision 2 of ADR 0003 (instruction text written by code) stays.

## Alternatives considered
- **Keep Gemini only, ration the quota.** Rejected: a step-by-step agent needs tens of calls per task while it is
  developed and tuned; 20/day per model would allow a handful of tasks.
- **Ollama's OpenAI-compatible endpoint (`/v1/chat/completions`).** Rejected: the native `/api/chat` takes a JSON
  schema in `format` directly and reports token counts; no extra SDK.
- **Use the local model in the product for cheap jobs.** Rejected for now: the reference laptop can't run it. The
  Phase 7 spike (#457) measures which jobs a local model could do; that would need its own decision.

## Consequences
- Easier: Phase 7 development and the spike run without using the Gemini quota.
- Harder: one more provider to maintain; results on a local 7B model are not results on Gemini, so every checkpoint
  and gate still runs on Gemini.
- `architecture.md` lists Ollama again, as an opt-in development provider.
