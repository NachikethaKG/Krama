# Phase 1: Verified workflow

**Goal:** the full loop from the UI, done safely: prompt → plan → human approval → execution → per-step verification → stored **Verified Workflow**. Failures are detected, never silently skipped; destructive actions pause; page text can't hijack the agent.

**Release tag:** `v0.1`

**Who builds what**
- **Vishwas:** the run engine: state machine, API + SSE, database, layered verifier, locator fallbacks, retry/replan.
- **Nachiketha:** the **safety layer** (`policy/`: risk, masking, CAPTCHA/auth-wall detection, prompt-injection defense), artifact capture, verifier accuracy measurement, and all the UI for it.

---

## Research before starting

**Vishwas**
- **State machines in Python:** the `transitions` library vs a hand-rolled enum + transition table. How do you persist state safely so a crash mid-run doesn't corrupt it?
- **SQLAlchemy 2 + Alembic:** async engine with psycopg 3, the session-per-request pattern in FastAPI, Alembic autogenerate and its limits (it misses some changes).
- **SSE in FastAPI:** `sse-starlette` vs `StreamingResponse`. How do you resume with `Last-Event-ID` (we store events in `run_events`)? Do you need heartbeats?
- **Agent recovery:** how do browser-use, Agent-E and SeeAct handle a failed step (retry the same action, re-locate the element, replan the rest)? What retry budget is sensible?
- **Vision grounding with Gemini:** how does Gemini return bounding boxes (normalized 0–1000, `[ymin, xmin, ymax, xmax]`)? How accurate is it on a Gitea screenshot? Turn a box into a Playwright click position.

**Nachiketha**
- **Prompt injection:** OWASP Top 10 for LLM Applications, LLM01 (prompt injection), especially *indirect* injection through web content. What defenses work: data delimiting, separate classifier, allow-listed actions?
- **CAPTCHA / bot-wall detection:** what do reCAPTCHA, hCaptcha and Cloudflare Turnstile / "Just a moment…" pages look like in the DOM (iframes, script URLs, titles)? How do you detect a login wall? (We detect and **stop**; we never bypass.)
- **Masking:** rrweb privacy options (`maskAllInputs`, `maskTextClass`, `blockClass`, `maskInputFn`). How do you mask sensitive values in screenshots (blur the element's bbox before saving)? Regex patterns for tokens/keys vs Microsoft **Presidio** for PII (does it run fast enough on CPU?).
- **Destructive-action classification:** keyword denylist (delete, transfer, publish, …) plus an LLM classifier. Where do false positives come from (e.g. "Delete draft" on a harmless page)? Which Gitea actions should count as destructive?
- **Frontend:** `EventSource` in React with reconnection, and a side-by-side screenshot diff UI.

**Together**
- What does "verified" mean? Agree on the confidence threshold and on which signals are enough per action type.
- Write the list of destructive Gitea actions together; it becomes the first policy test set.

---

## Sprint 1.1: plan → approve → execute end to end

| Vishwas | Nachiketha |
|---|---|
| `runs/`: state machine (`draft → approved → running → verified/failed/paused/cancelled`) + in-process executor | `observer/`: persist captures and recordings through the `ArtifactStore` port |
| `api/`: `/tasks`, `/plans`, `/plans/{id}/approve`, `/runs`, SSE `/runs/{id}/events` | Frontend: switch from mock to the real API behind `NEXT_PUBLIC_API_MODE` |
| `db/`: models + first Alembic migrations, `run_events` table | Frontend: plan editing (reorder / delete / edit text), cancel button, error and paused states |
| `storage/`: `LocalFsStore` + `/artifacts` endpoint, export `openapi.json` | |

## Sprint 1.2: verification and recovery

| Vishwas | Nachiketha |
|---|---|
| `verifier/`: layered verifier (URL/DOM → ARIA → network → Gemini vision last), with confidence | `benchmarks/`: **failure-injection set** (deliberately broken steps, wrong pages) to measure verifier accuracy: does it catch every failure? |
| `agent/`: locator fallback chain (role/name → text → ARIA → vision bbox) | Frontend: failure and replan UI ("Expected X / Observed Y", screenshots side by side) |
| `runs/`: retry → replan loop with a retry budget and timeout; fail-safe pause | Frontend: run history list, workflow detail page with each step's verification evidence |

## Sprint 1.3: safety baseline

| Vishwas | Nachiketha |
|---|---|
| `runs/` + `api/`: wire the `Policy` port into the executor: `paused` state, `/runs/{id}/confirm`, resume/deny | `policy/`: denylist + LLM risk classifier for plans and individual actions |
| `planner/` + `llm/`: pass page text as clearly delimited **data**, never as instructions | `policy/`: CAPTCHA / bot-wall / auth-wall detection → stop the run |
| Run the injection test page through the full agent | `policy/`: masking for inputs, rrweb and screenshots **before** storage and before any LLM call |
| | `policy/` tests: a local **prompt-injection test page** (hidden "ignore previous instructions" text) |
| | Frontend: confirmation modal for paused destructive steps, "Automation restricted → Take over manually" screen |

## Exit criteria
- On Nachiketha's laptop, the UI runs "create a repo": plan → approve → live view → stored verified workflow.
- A deliberately broken step is detected (never silently continued), and the failure-injection benchmark reports verifier accuracy.
- A destructive step pauses for confirmation.
- The hidden-text injection page doesn't change the agent's behaviour.
- No password or token appears in any stored artifact (checked by a test).
