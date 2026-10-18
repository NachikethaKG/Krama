# 0003 — No local model (Ollama) for text jobs; instruction text comes from code

- **Status:** accepted
- **Deciders:** Vishwas (research and decision), Nachiketha (review)
- **Issue:** #74 · Research: [`phase-2-vishwas-local-model.md`](../research/phase-2-vishwas-local-model.md),
  [`phase-2-vishwas-instruction-text.md`](../research/phase-2-vishwas-instruction-text.md) (#68)

## Context
`architecture.md` planned an optional `OllamaProvider` for cheap text jobs (captions, step descriptions), switched on
with `LLM_PROVIDER_TEXT=ollama`. Nothing implements it: the variable is only in `.env.example`. Phase 2 asked whether
it is worth building, using the one text job we have now, rewriting each step's instruction text after a run.

The test (2026-10-16/18, assets in `docs/research/assets/phase-2-vishwas-instruction-text/`): 22 real executed steps
from 5 Gitea tasks, one call per workflow, the same prompt and the same automatic checks for every provider, plus a
template written in plain code as the baseline.

| | Steps passing all checks | Same text as the template | Time per workflow | Needs |
|---|---|---|---|---|
| Template (code, no LLM) | 22/22 | — | 0 s | nothing |
| gemini-3.8-flash | 22/22 | 16/22 | 6–53 s | free-tier quota (20 requests/day per model) |
| gemini-3.5-flash | 22/22 | 16/22 | 6–47 s | free-tier quota |
| gemini-2.5-flash | 9/9 answered | — | 8–11 s | quota (ran out mid-test) |
| Llama 3.1 8B, Ollama, RTX 4050 | 19/22 | 7/22 | 8–18 s | a 6 GB GPU (5.9 GB loaded) |

- On structured step data, every model writes essentially what the template writes. Where Gemini 3.x differs from
  the template (6 steps), it is worse: it copies raw page titles ("Go to the **Issues - krama-research-tasks**
  page"). Llama 3.1 adds its own mistakes ("enter **Description** with `…`", multi-line file content pasted inline).
- The steps that read badly (e.g. "Under **Labels Milestones**, …", "**Editor content**") come from poor context
  data, and no model fixed them.
- **Nachiketha's laptop, the reference machine, cannot run Ollama models** (checked by Vishwas on the laptop,
  2026-10-16). CPU-only on Vishwas's laptop: same text, about 4× slower, 5.2 GB RAM.

## Decision
1. **Don't build an `OllamaProvider`.** Remove `LLM_PROVIDER_TEXT`, `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from
   `.env.example`, and the Ollama mentions from `architecture.md`.
2. **Instruction text is written by code:** the planner prompt gets the style rules for plan-time text, and a
   deterministic post-run rewrite builds each step's text from the executed step and its DOM context (#73).
3. Gemini stays the only real `LLMProvider`. If a later text job needs an LLM, it uses Gemini through the existing
   interface.

## Alternatives considered
- **Keep Ollama as an opt-in for Vishwas's GPU only.** Rejected: it would be one more provider to test and maintain
  for a job the template does as well, on a machine that isn't the reference; and anything that only works on one
  laptop can't be part of a demo.
- **Use Gemini for the rewrite.** Rejected as the default: no better than the template on this data, slower
  (up to 53 s per call), and every call uses the 20/day free-tier quota that planning and vision also need.
  It stays possible later as an optional polish, with a screenshot (the one input a template can't use).

## Consequences
- Easier: the text job is free, offline, deterministic and unit-testable; no quota use; same output on both laptops.
- Harder: wording quality depends on the context we extract (dialog, menu, section heading). #73 has to improve that
  extraction, since no model compensates for it.
- `architecture.md` §2, §3, §4 and §6 no longer list Ollama (changed in the same PR as this ADR). The `LLMProvider`
  seam is unchanged, so adding a local provider later needs no architecture change, only a new ADR superseding this one.
- `AGENTS.md` rule 10 ("Ollama/local models are opt-in only") stays true as written.
