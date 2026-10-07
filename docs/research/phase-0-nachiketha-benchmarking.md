# Benchmarking web agents: success definition and what the harness records

- **Phase:** 0
- **Researched by:** Nachiketha (research done by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha, the exit-gate rules by both)
- **Question(s):** How do WebArena / Mind2Web define task success? What should our harness record per run (success, steps, retries, time, LLM calls)?

## Findings
**WebArena** (Zhou et al., 2023) [verified: https://arxiv.org/html/2307.13854]
- 812 tasks from 241 templates. Success is **functional correctness of the final site state**, not the path taken.
  - Information tasks: `exact_match`, `must_include` or `fuzzy_match` (an LLM judge) against a reference answer.
  - Tasks that change the site: a **program** reads the result (DB query, site API, JS selector) and checks it.
- GPT-4 agent 14.41%, humans 78.24%.

**Mind2Web** (Deng et al., 2023) [verified: https://arxiv.org/html/2306.06070]
- 2,000+ tasks on 137 sites, evaluated **offline** on cached pages, with the correct previous actions given at each step.
- Metrics: element accuracy, operation F1, **step success rate** (element + operation correct), **task success rate** (all steps correct).
- **Online-Mind2Web** (2025): 300 live tasks; an LLM judge (WebJudge) agrees with humans ~85%. Live success rates are much lower than offline ones [verified: https://arxiv.org/abs/2504.01382]

**AgentLab / BrowserGym** logs per-step information and screenshots, collects episode summaries into a table, and keeps a reproducibility journal (package versions, commit hash). Resetting a WebArena instance takes ~5 minutes, so it runs studies sequentially [verified: https://github.com/ServiceNow/AgentLab]

**Gitea gives us a WebArena-style program check** [verified locally: anonymous `curl` against local Gitea 1.22.6]:
- `GET /api/v1/repos/demo/<name>` → `200` with `"empty": false` for a repo created with *Initialize Repository*; `404` if it doesn't exist.
- `GET /api/v1/repos/demo/<name>/contents/README.md` → `200` when the README exists.
- Both work without auth for public repos; private repos would need a token.

**What 8/10 means statistically** (Wilson 95% interval, n = 10) [verified locally: computed]:

| Successes | 95% interval for the true success rate |
|---|---|
| 7/10 | 0.40–0.89 |
| 8/10 | 0.49–0.94 |
| 9/10 | 0.60–0.98 |
| 10/10 | 0.72–1.00 |

If the true success rate is 0.8, a 10-run batch reaches ≥ 8/10 only ~68% of the time (0.9 → ~93%, 0.7 → ~38%). The gate is a smoke test, not a precise measurement.

**Quota** (from the Gemini research, `phase-0-vishwas-gemini-structured-output.md`): 5 requests/min and 20 requests/day per model, three models in the fallback chain, so ~60 requests/day. 10 runs fit in a day only if a run averages ≤ 6 LLM calls, including retries and fallbacks.

## Recommendation
**Exit-gate rules (decided together by Vishwas and Nachiketha on 2026-10-07, research issue #27):**
- **≥ 8/10** planned runs in **one batch** on Nachiketha's laptop.
- **Success = an independent final-state check by the harness** (Gitea API: repo exists, not empty, README present) **and** every step verified by our verifier. The agent never grades itself.
- Runs that fail **only** because Gemini is unavailable or out of quota (all models 503/429) are recorded as `infra`/`quota`, **excluded and re-run**. More than 2 exclusions invalidate the batch.

**Harness design (proposed, pending Nachiketha's decision; issues #38, #39):**
- **One JSONL line per run**, with these fields:
  - identity: `run_id`, `task_id`, `task_file_sha`, `attempt`, `started_at`, `git_sha`, `gitea_version`, `viewport`, `headless`
  - models: `models_tried[]` (`{model, status, http_code, latency_ms, tokens_in, tokens_out}` per call), `final_model`, `fallback_count`, `llm_calls_total`, `llm_calls_failed`, `tokens_in`, `tokens_out`
  - plan: `steps_planned`, `steps_executed`, `replans`, `retries_total`
  - per step: `steps[]` = `{seq, action, target, duration_ms, retries, verification: {result, method}, error}`
  - outcome: `success_external`, `success_agent`, `success` (both true), `failure_category` (`planning | locator | verification | timeout | quota | infra | none`, the first failure in causal order)
  - time: `duration_ms_total`, `duration_ms_planning`, `duration_ms_execution`
  - artifacts: `artifacts_dir` (run log, observer captures, rrweb recording)
- **Report per task:** `k/n` + Wilson 95% interval, median and p90 duration, mean LLM calls and tokens, a count per failure category, how often our verifier and the external check agree, and how many runs were excluded as quota/infra.
- **Independent runs:**
  - a unique repo name per run (`krama-bench-<short run id>`), passed into the task text
  - delete it after the run with the Gitea API
  - delete leftover `krama-bench-*` repos before a batch
  - a fresh browser context per run
  - `just reset-gitea` once per batch, not per run
- **Quota:** run batches sequentially with ≥ 12 s between LLM calls; stop the batch with `quota_exhausted` instead of counting runs as failures. CI dry runs use the fake LLM provider.
- **Plan approval:** the harness auto-approves the plan, so it measures plan + execute + verify, not human latency.

## Open questions
- How many LLM calls does a typical Gitea run make once replanning exists (Phase 1)? It decides whether 10 runs still fit in one day.
- Deleting repos needs an API token for `demo`. Should `just seed` create one, or should the harness use the admin account?

## Links
- https://arxiv.org/abs/2307.13854 (WebArena)
- https://arxiv.org/abs/2306.06070 (Mind2Web)
- https://arxiv.org/abs/2504.01382 (Online-Mind2Web)
- https://github.com/ServiceNow/AgentLab
- https://docs.gitea.com/api/1.22/
