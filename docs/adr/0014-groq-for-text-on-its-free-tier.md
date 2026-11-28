# 0014 — Groq as a supported provider for text jobs; Gemini stays the default

- **Status:** accepted (adds to [ADR 0003](0003-no-local-model-for-text-jobs.md) and
  [ADR 0010](0010-local-llm-as-opt-in-dev-provider.md))
- **Deciders:** Vishwas (2026-11-28)
- **Issue:** #482 (found by the Phase 7 exit gate)

## Context
In the exit gate, Gemini's free tier was the bottleneck:

- Each model allows **20 requests a day** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`).
- gemini-3.8-flash answered only 503 for days and left the default list (#507).
- On 2026-11-28 gemini-3.5-flash answered only 503 as well, leaving one model with about 20 calls.
- A step-mode task needs 5–12 calls, so the free tier gave 2–4 tasks a day. The 24-task gate would have taken about
  two weeks, and a free-tier user gets the same few tasks a day.

Groq has a free tier through an OpenAI-compatible API. Its own rate-limit headers (2026-11-28) report, per model:

- 1,000 requests a day;
- 8,000 tokens a minute, which also caps a single request.

Its free models are `openai/gpt-oss-120b`, `qwen/qwen3.8-27b` and `openai/gpt-oss-20b`. They are text only: there is
no vision model on a free key.

A spike on the 16 public gate tasks (`benchmarks/results/real-sites-groq/`) gave these results:

- **4 of the 8 tasks Krama could attempt passed fully** (Wiktionary ×2, httpbin ×2): verified, and replayed without
  an LLM. Each took 20–80 s and 5–7 calls, with about 1 s per decision.
- The rest:
  - **Internet Archive ×2:** one request was too big (9,000+ tokens), which the smaller page budget below fixes.
  - **the-internet ×2:** unnamed controls needed vision, and Gemini was out of quota that day.
  - **The other 8:** CAPTCHA sites (replaced in #511) or a site that was down.
- The model on PyPI's image CAPTCHA tried to interact with it. That led to #509 (the policy stops at a named CAPTCHA)
  and #510 (the step agent never touches one). Both apply to every provider.

## Decision
- **`LLM_PROVIDER=groq`** is a supported option:
  - Text jobs (outlines, step decisions, the task check, the policy classifier, replans) go to Groq through
    `OpenAICompatProvider`, which falls back across `GROQ_MODELS`.
  - Images (vision locator, vision verifier) still go to Gemini through `SplitProvider`, so keep `GEMINI_API_KEY`.
    Without it, vision is off, as with Ollama.
- **Gemini stays the default.** Groq is opt-in.
- **Per-minute limits are waited out, not counted as quota.** A 429 for tokens a minute moves to the next model. When
  every model is busy, Krama waits for the first to free up, for up to 60 s in all. Only a per-day 429 counts as quota
  (`quota_exhausted`), so the benchmark's guard only stops for that.
- **Smaller page with Groq.** The page snapshot an LLM sees is `PAGE_BUDGET_CHARS`: 24,000 characters (about 6,000
  tokens) by default, and 14,000 with groq, so one decision stays under Groq's 8,000-token request cap.
- **Results name their model.** Gate and benchmark results from Groq runs are kept apart from Gemini runs
  (`real-sites-groq/`). The exit-gate write-up says which provider produced which result.

## Consequences
- A free-tier user can run many more tasks a day: about 1,000 requests per model instead of 20.
- Groq sees less of a big page (14,000 characters). On very long pages the element a task needs may fall outside
  that, as can already happen at 24,000. The trimming keeps dialogs and the start of the page.
- Two providers mean two keys and two sets of terms. Groq's free-tier terms apply to text jobs. As with Gemini, page
  text is untrusted data, and passwords and secrets are masked before any LLM sees a page (AGENTS.md §4).
- The `OpenAICompatProvider` also fits other OpenAI-compatible APIs (Cloudflare Workers AI, OpenRouter, GitHub
  Models) if one of them is wanted later. That would be a new decision, not covered here.
- If Groq changes its free tier, `LLM_PROVIDER=gemini` still works unchanged.
