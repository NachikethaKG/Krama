# Architecture (v1, frozen)

> **Frozen:** changes need an ADR in `docs/adr/` and approval from both. Product roadmap: [`phases/`](phases/README.md).

## 1. Pipeline

```
Next.js UI (prompt / plan review / live view / tutorial player)
      │  REST + SSE  ── docs/api-contract.md, contracts/
FastAPI ── Run state machine ── Planner (LLM) ── Policy (risk / denylist)
      │
Browser worker (Playwright Python, headless Chromium, CPU-only)
      ├─ Observer: URL, DOM, ARIA snapshot, screenshot, network, rrweb events
      ├─ Locator:  role/name → text → ARIA → vision fallback (LLM)
      └─ Verifier: cheapest reliable signal first (URL/DOM → ARIA → network → vision)
      │
Postgres (tasks, plans, runs, workflows, steps)  +  data/artifacts/ (screenshots, rrweb)
      │
Verified Workflow JSON ──► tutorial-compiler (TS, pure function) ──► TutorialSpec ──► Player
                                                                        └──► Remotion MP4 (Phase 5)
```

**The Verified Workflow is the core object.** The tutorial, text guide, video and (later) "do it for me" are all *outputs* compiled from it.

## 2. Stack (pinned)

| Layer | Choice | Version pin |
|---|---|---|
| Backend | Python, uv, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic | `.python-version` (3.12) |
| Browser | Playwright for Python, headless Chromium | `backend/uv.lock` |
| LLM | `LLMProvider` interface: Gemini (reference), Ollama (opt-in), Fake (tests) | — |
| Jobs | In-process asyncio (Phases 0–2) → Redis + arq (Phase 3) | Redis 7 |
| Frontend | Next.js (App Router), TypeScript, Tailwind, pnpm | `.nvmrc` (Node 22), `packageManager` field |
| Replay | rrweb recording + SVG overlay layer | `pnpm-lock.yaml` |
| TTS | Web Speech API → Piper (CPU) later | — |
| Video | Remotion + FFmpeg (Phase 5) | — |
| DB | PostgreSQL 16 (Docker) | `infra/docker-compose.yml` |
| Test target | Gitea (Docker), then real GitHub (Phase 3) | `infra/docker-compose.yml` |
| CI | GitHub Actions, ubuntu, no GPU | `.github/workflows/ci.yml` |

## 3. Backend module layout (`backend/app/`)

Ownership is by module ([ADR 0001](adr/0001-ownership-by-module.md)). Modules owned by different people talk **only through `ports/`**.

| Module | Owner | Responsibility |
|---|---|---|
| `ports/` | both (contract) | Python `Protocol` interfaces between modules owned by different people (`Observer`, `Policy`, `Validator`, `Exporter`, …) |
| `api/` | Vishwas | FastAPI routers. Thin: validate the request, call a service, return a contract model |
| `runs/` | Vishwas | Run state machine `draft → approved → running → verified/failed/paused/cancelled`, executor |
| `planner/` | Vishwas | Task interpretation + plan generation (`instruction_text`, `expected_state` per step) |
| `agent/` | Vishwas | Browser session, action execution, locator fallback chain, self-healing (Phase 4) |
| `verifier/` | Vishwas | Compares expected vs observed state, returns result + method + confidence |
| `llm/` | Vishwas | `LLMProvider` + Gemini / Ollama / Fake implementations, prompt templates |
| `db/` | Vishwas | SQLAlchemy models, repositories, Alembic migrations (schema: [`database-schema.md`](database-schema.md)) |
| `storage/` | Vishwas | `ArtifactStore` (local FS → S3 later) |
| `tts/` | Vishwas | Piper narration audio (Phase 5) |
| `observer/` | Nachiketha | Captures page state after each action (URL, ARIA, screenshot, network) and the rrweb recording + timing alignment |
| `policy/` | Nachiketha | Risk classification, destructive-action pause rules, CAPTCHA/auth-wall detection, sensitive-data masking, prompt-injection defense |
| `validation/` | Nachiketha | Scheduled re-runs of stored workflows, UI drift detection (Phase 4) |
| `export/` | Nachiketha | Video export jobs that drive `packages/video-exporter` (Phase 5) |
| `contracts_gen/` | generated | Generated Pydantic models. **Never hand-edit** |

Outside `backend/app/`: `benchmarks/` (harness, metrics, reports) is Nachiketha's; `benchmarks/tasks/` is shared.

## 4. Mock seams (nobody waits for anybody)

Every boundary is an interface with a mock that ships *before* the real implementation. Code depends on the interface, so moving from mock to real needs no architectural change.

| Seam | Interface | Mock (exists first) | Real | Who uses the mock |
|---|---|---|---|---|
| LLM | `LLMProvider` | `FakeProvider`: replays `backend/tests/llm_fixtures/*.json` | `GeminiProvider`, `OllamaProvider` | backend tests, CI, offline dev |
| Planner | `Planner` | `StaticPlanner`: returns a fixture plan | `LLMPlanner` | executor + API work before the planner is good |
| Browser | `BrowserSession` | `RecordedSession`: replays stored observations | `PlaywrightSession` | verifier/policy unit tests |
| Verifier | `Verifier` | `ScriptedVerifier`: results given by the test | `LayeredVerifier` | executor/replan tests |
| Executor | `RunExecutor` | `InProcessExecutor` | `ArqExecutor` (Phase 3) | everything before Redis jobs |
| Artifacts | `ArtifactStore` | `LocalFsStore` | S3/MinIO (later) | — |
| Backend API | `ApiClient` (TS) | `MockApiClient`: serves `contracts/fixtures/`, replays SSE with real timings | `HttpApiClient` | the whole frontend until the backend is ready (`NEXT_PUBLIC_API_MODE=mock`) |
| Narration | `Narrator` (TS) | `SilentNarrator` | `WebSpeechNarrator`, Piper | player tests |

**Rule:** a mock must return data that **validates against the contract schema**. A mock that drifts from the contract is a bug.

## 5. Key decisions

| Decision | Why | ADR |
|---|---|---|
| Real UI capture, never generated UI | Software tutorials need exact fidelity | PRD |
| Plan → Approve → Execute | Human control before any risky action | PRD |
| Gemini as the reference LLM on both laptops | Same behaviour everywhere; no GPU on Nachiketha's laptop | — |
| Gitea first, GitHub later | Resettable, deterministic, no bot walls or login | — |
| Tutorial compiler in TypeScript | Shared by the player and the Remotion export | — |
| DB migrations owned by Vishwas only | Two people writing migrations is a classic source of conflicts | — |
| Ownership by module, cross-owner calls only via `ports/` | Both people work on the backend without sharing files | [0001](adr/0001-ownership-by-module.md) |

## 6. Hardware rules

- No GPU anywhere in the default path. Ollama is opt-in (`LLM_PROVIDER_TEXT=ollama`).
- Chromium is headless in tests. Headed mode is only for manual login/debugging.
- `MAX_CONCURRENT_RUNS=1` locally. Docker is limited to 4GB through `.wslconfig`.
- CI (ubuntu, no GPU) is the automatic stand-in for "runs on Nachiketha's laptop".
