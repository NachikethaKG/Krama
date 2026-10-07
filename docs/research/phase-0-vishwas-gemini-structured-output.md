# Gemini: structured output, free-tier limits and 429 handling

- **Phase:** 0
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** The `google-genai` SDK and structured output (`response_schema` / JSON mode) to get a plan as valid JSON. What are the free-tier limits (requests per minute and per day) for the Flash model? How do you handle `429` errors?

## Findings
- Tested with **google-genai 2.28.0**, Pydantic 2.13.5, Python 3.12, on 2026-10-07. Script and raw results: [`assets/phase-0-vishwas-gemini/`](assets/phase-0-vishwas-gemini/) [verified locally]
- Flash models the key can call (`GET /v1beta/models`): `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.8-flash`, `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`, plus the aliases `gemini-flash-latest` / `gemini-flash-lite-latest`. All have a 1,048,576-token input limit [verified locally]

**Structured output**
- `GenerateContentConfig` has two schema fields: `response_schema` (the SDK's own OpenAPI-style `Schema`, or a Pydantic class it converts) and `response_json_schema` (plain JSON Schema), plus `response_mime_type="application/json"` [verified locally: SDK model fields]
- **`response_schema=<our generated Pydantic model>` fails**: `400 INVALID_ARGUMENT … Unknown name "additional_properties" at 'generation_config.response_schema…'`. Our contract models all have `extra="forbid"` (`additionalProperties: false`), which the older `Schema` format rejects [verified locally]
- **`response_json_schema=PlanOut.model_json_schema()` works.** `PlanOut` is `{steps: list[PlannedStep]}`, with `PlannedStep` taken unchanged from `app.contracts_gen`. The schema has `$defs`/`$ref`, `anyOf` with `null`, and `additionalProperties: false` [verified locally]:

  | Model | Result | Steps | Time | Tokens (prompt / output / thinking) |
  |---|---|---|---|---|
  | `gemini-2.5-flash` | **valid against the contract** | 4 | 4.7 s | 701 / 648 / 207 |
  | `gemini-3.5-flash` | **valid against the contract** | 4 | 4.6 s | 701 / 557 / 449 |
  | `gemini-3.8-flash` | `503 UNAVAILABLE` "high demand" (3 tries), then `500 INTERNAL` | — | — | — |
  | `gemini-flash-latest` | `503 UNAVAILABLE` (4 attempts) | — | — | — |

- Both valid plans matched the Phase F walkthrough: they used the dashboard's *New Repository* link (the alternative path the walkthrough accepts), copied `"Repository Name *"` exactly, used path-only `url_matches` (`^/repo/create$`, `^/demo/demo-repo$`), `field_values` after `fill`, `checked` after the checkbox, and rated the final click `medium` risk. No step had an empty `expected_state` [verified locally: [`plan-gemini-2.5-flash.json`](assets/phase-0-vishwas-gemini/plan-gemini-2.5-flash.json), [`plan-gemini-3.5-flash.json`](assets/phase-0-vishwas-gemini/plan-gemini-3.5-flash.json)]
- `ExpectedState.minProperties: 1` is **not** enforced by the generated Pydantic model (known limit, `contracts/README.md`), so the planner must check it itself [verified: contracts/README.md]
- Prompt shape that was used: trusted system instructions, then the task, `<site_hints>` and the dashboard ARIA snapshot inside `<page_snapshot untrusted="true">` (see the planning-prompts note) [verified locally]

**Free-tier limits**
- The official rate-limits page (last updated 2026-09-02) **no longer lists free-tier numbers**; it says to check AI Studio. It also says limits are applied **per project, not per API key**, and requests-per-day reset at midnight Pacific [verified: https://ai.google.dev/gemini-api/docs/rate-limits]
- **Measured:** a burst of back-to-back calls to `gemini-2.5-flash` got a 429 after 7 successes (calls from an earlier burst in the same minutes also counted). The error states the limit [verified locally: [`burst-429-gemini-2.5-flash.json`](assets/phase-0-vishwas-gemini/burst-429-gemini-2.5-flash.json)]:
  - `quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier`, `quotaValue: "5"`, so **5 requests per minute per project per model**
  - `RetryInfo.retryDelay: "9s"` and the message "Please retry in 9.546788189s"
- Requests per day for the free tier: **not measured** [unverified]. Check https://ai.dev/rate-limit (AI Studio) for the project.
- Gemini also returned **503 UNAVAILABLE** ("high demand") on `gemini-2.5-flash` during the burst and repeatedly on `gemini-3.8-flash`. These are transient server errors, not quota errors [verified locally]

**429 / retry handling in the SDK**
- **The SDK does not retry by default.** With no `retry_options`, it makes a single attempt (`stop_after_attempt(1)`) [verified locally: `google/genai/_api_client.py` `retry_args`]
- Opt-in: `HttpOptions(retry_options=HttpRetryOptions(...))`. Defaults: 5 attempts, 1 s initial delay, 60 s max, exponential base 2, jitter 1, on HTTP 408/429/500/502/503/504 [verified locally: same file]
- The SDK **ignores the server's `RetryInfo.retryDelay`**; its backoff is its own exponential schedule [verified locally: no `retryDelay` handling in the SDK source]

**Configuration pitfall**
- A stale `GEMINI_API_KEY` set in the Windows user environment caused `400 API_KEY_INVALID` although the `.env` file had a valid key. Both python-dotenv (without `override=True`) and **pydantic-settings 2.15 let the OS environment win over `.env`** [verified locally]
- `app/config.py` reads the **repo-root** `.env`, not `backend/.env` [verified locally]

## Recommendation
Proposed (pending Vishwas's decision):
- **Model:** `gemini-2.5-flash` as the default (`GEMINI_MODEL`, already in `.env.example`). It's stable, it produced a contract-valid plan, and it was the one Flash model that answered reliably today. Keep the model name in config, so switching to `gemini-3.5-flash` or newer is one line.
- **Schema:** `GeminiProvider` (#34) passes `response_json_schema=<Pydantic model>.model_json_schema()` and validates the reply with `model_validate_json`. Never `response_schema` with our `extra="forbid"` models. LLM-facing models contain only what the model decides (steps); ids, status and timestamps are added by our code.
- **Retry:** our own small retry in `GeminiProvider` instead of the SDK's: on 429, wait `RetryInfo.retryDelay` (fallback: exponential); on 500/503/504, exponential backoff with jitter; at most ~4 attempts; then raise a typed `LLMRateLimited` / `LLMUnavailable` error. Count every attempt for the benchmark's "LLM calls" metric. Optionally add a client-side limiter (5 requests/min) so the 10-run benchmark doesn't hit 429 at all.
- **Keys:** keys go in the **repo-root** `.env`. Remove stale `GEMINI_API_KEY` / `GOOGLE_API_KEY` from the OS environment. Keep the pydantic-settings default (OS env wins), but log which source the key came from (never the key itself) at startup.

## Open questions
- Free-tier **requests per day** for `gemini-2.5-flash`: look up at https://ai.dev/rate-limit. It decides how many benchmark runs fit in a day.
- **For #27 (Together):** limits are per **project**, not per key. Two keys in the same Google Cloud project share one quota, so Vishwas and Nachiketha need keys in separate projects.
- Does `gemini-3.8-flash` become reliable? Re-test before the exit gate; it's the model the current docs use in their examples.

## Links
- https://ai.google.dev/gemini-api/docs/structured-output
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.dev/rate-limit
- https://github.com/googleapis/python-genai
- https://docs.pydantic.dev/latest/concepts/pydantic_settings/
