# Local model (Ollama) vs Gemini for the instruction-text job

- **Phase:** 2
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **Local model test:** run the same instruction-text prompt on your RTX 4050 with Ollama (Llama 3.1 8B / Qwen 2.5 7B) vs Gemini Flash. Is the local output good enough for this one cheap text job? (This decides whether `LLM_PROVIDER_TEXT=ollama` is worth keeping.)

## Findings
Same prompt, same 22 steps and same checks as in [`phase-2-vishwas-instruction-text.md`](phase-2-vishwas-instruction-text.md).
Ollama 0.17.1 on Windows 11, RTX 4050 Laptop (6 GB), temperature 0, JSON-schema constrained output through
`/api/chat` `format` [verified: https://docs.ollama.com/capabilities/structured-outputs]. Only **Llama 3.1 8B** was
tested, by Vishwas's decision. Qwen 2.5 7B was dropped from the test. Outputs:
[`assets/phase-2-vishwas-instruction-text/`](assets/phase-2-vishwas-instruction-text/).

**Nachiketha's laptop can't run Ollama models.** Vishwas checked this on the laptop itself (2026-10-16). So a local
model can only ever be an opt-in on Vishwas's machine, never the default or anything the demo depends on
(`AGENTS.md` rule 10 already says so).

| | Llama 3.1 8B on GPU | gemini-2.5-flash | Template (no LLM) |
|---|---|---|---|
| Steps passing all checks | 19/22 | 9/9 answered (quota ran out after 2 of 5 workflows) | 22/22 |
| Time per workflow | ≈ 11 s (56 s for 5; model loaded) | 7.6 s and 11.3 s (the 2 answered) | 0 s |
| JSON valid, one entry per step | 5/5 workflows | 2/2 answered | — |
| Memory | 5.9 GB, split 93% GPU / 7% CPU (`ollama ps`) | — | — |
| Free-tier quota | none needed | 20 requests/day per model (Phase 0 note), used up on the test day | none |

[verified locally: `out-ollama-llama3.1-8b.json`, `out-gemini-gemini-2.5-flash.json`, `out-template.json`]

- **Quality:** where both answered, Llama 3.1 wrote exactly the same sentence as Gemini 2.5 on **8 of 9** steps.
  Its 3 failed checks: the two dialog steps name the dialog without bold (cosmetic) and the multi-line file content
  is pasted into the sentence. The checks don't catch one real wording error: "enter **Description** with
  `Docs for the team`".
- **For this job the model barely matters.** With structured step data, the template already gives the same text,
  and the poor steps come from the input data (see the instruction-text note), which no model fixed.
- One CPU-only run (`num_gpu: 0`) was made before the decision above: same text, 232 s for 5 workflows plus about
  40 s model load, 5.2 GB RAM [verified locally: `out-ollama-cpu-llama3.1-8b.json`]. Kept only as a data point.
- **Not tested:** Gemini 3.x (quota used up on the test day), more prompt variants, and Llama with a screenshot
  (Llama 3.1 8B is text-only).

## Recommendation
For the ADR (#74), decision is Vishwas's:
- **Don't add an `OllamaProvider` for Phase 2, and drop `LLM_PROVIDER_TEXT` from `.env.example`** (today it's a
  documented variable that nothing reads). Reasons: the template does the instruction-text job as well, for free and
  offline; the one local model tested is no better than Gemini; and the reference laptop can't run it anyway.
- Keep the `LLMProvider` seam as it is. If a future text job (e.g. Phase 5 narration scripts) needs free local
  generation on Vishwas's GPU, a ~40-line provider like the `Ollama` class in `instruct.py` fits behind the existing
  interface without architecture changes.
- No `architecture.md` change needed. If the ADR drops the opt-in, the "Ollama (opt-in)" mentions in
  `architecture.md` §2/§4/§6 become stale; changing them needs the ADR plus both owners' approval.

## Open questions
- Re-run the Gemini 3.x side after the quota reset, so the ADR has a full Gemini column (planned with the
  instruction-text rerun).

## Links
- https://docs.ollama.com/capabilities/structured-outputs
- https://ai.google.dev/gemini-api/docs/rate-limits
- `docs/research/phase-0-together-gemini-keys-and-reliability.md` (free-tier limits)
