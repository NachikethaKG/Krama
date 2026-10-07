# Gemini keys per person, and what "reliably" means for the exit gate

- **Phase:** 0
- **Researched by:** Together (run by Claude Code on Vishwas's laptop with Nachiketha present; the exit-gate rules decided by both on 2026-10-07)
- **Question(s):**
  - Both create a Gemini API key (one each; limits are per key) and run one structured-output call from Python to confirm quota.
  - Agree on the definition of "reliably" for the exit gate (proposed: ≥ 8 of 10 runs).

## Findings
**Keys and quota**
- **Limits are per Google Cloud project, not per key.** Two keys in the same project share one quota [verified: https://ai.google.dev/gemini-api/docs/rate-limits; see `phase-0-vishwas-gemini-structured-output.md`]. So each person needs a key in **their own project** to get their own quota.
- Free tier per project, per model: **5 requests/min, 250K tokens/min, 20 requests/day**, the same for `gemini-3.8-flash`, `gemini-3.5-flash` and `gemini-2.5-flash` [verified: AI Studio rate-limit page, Vishwas's project, 2026-10-07]
- **Vishwas's key:** a structured-output call (Pydantic schema through `response_json_schema`) returned a valid 3-step plan with `gemini-2.5-flash` (568 tokens, 4.2 s). `gemini-3.5-flash` returned `503 UNAVAILABLE` twice, so the fallback order 3.8 → 3.5 → 2.5 is needed [verified locally: [`key_check.py`](assets/phase-0-together-gemini-keys/key_check.py), [`vishwas-result.json`](assets/phase-0-together-gemini-keys/vishwas-result.json)]
- **Nachiketha's key:** not checked yet. He runs the same script on **his** laptop (the exit-gate machine). See the open questions.
- Keys go in the **repo-root `.env`** (`GEMINI_API_KEY`). A `GEMINI_API_KEY` set in the OS environment overrides `.env`, so remove any old one [verified locally: see the Gemini note]

**How strong is ≥ 8/10?** [verified locally: computed; see `phase-0-nachiketha-benchmarking.md`]
- 8/10 → 95% interval for the true success rate **0.49–0.94**.
- If the true rate is 0.8, a single 10-run batch passes ≥ 8/10 only ~68% of the time. The gate is a smoke test, not a precise measurement.

## Recommendation
**Decided by Vishwas and Nachiketha (2026-10-07):**
- **Reliably = ≥ 8 of 10 planned runs succeed, in one benchmark batch, on Nachiketha's laptop.**
  - Planned means the plan comes from the LLM planner, not a hardcoded script.
  - Gitea is reset before the batch, and each run uses its own repo name.
- **Success is judged independently:** the harness checks Gitea's final state through its API (repo exists, not empty, README present) **and** every step was verified by our verifier. The agent never grades itself.
- **Quota/infra failures don't count against the agent:** a run that fails only because every Gemini model returned 503/429 is recorded as `quota` / `infra`, excluded and re-run. The report shows how many runs were excluded; **more than 2 exclusions invalidate the batch**.
- Suggested change to `docs/phases/phase-0-spike.md` (not applied here): add these three rules to the exit criteria.

## Open questions
- **Nachiketha (on his laptop):**
  1. Create a key at https://aistudio.google.com/apikey with **"Create API key in new project"**.
  2. Put it in his repo-root `.env` as `GEMINI_API_KEY=...`.
  3. Save the key alone in a temporary file and run `cd backend && uv run python ../docs/research/assets/phase-0-together-gemini-keys/key_check.py nachiketha <key-file> gemini-2.5-flash`, then delete the file.
  4. Add the result and his https://ai.dev/rate-limit table to this note.

## Links
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.dev/rate-limit
- https://aistudio.google.com/apikey
