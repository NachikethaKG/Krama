# Phase F: Foundation

**Goal:** a repo where two people and two AI agents can work in parallel safely: guardrails, environment, skeletons, and the **contracts v1** that let both sides build against each other before either side is finished.

**Release tag:** `v0.0-foundation`

| Sprint | Status |
|---|---|
| F1: repo and guardrails | ✅ done (PR #3) |
| F2: contracts v1 | next |

---

## Sprint F1: repo and guardrails ✅

Done together on one laptop. Delivered: `AGENTS.md`, `OWNERSHIP.toml`, CODEOWNERS, ownership and commit-message hooks, CI, Docker services (Postgres, Redis, Gitea), `just setup|up|seed|dev|check`, FastAPI `/health` skeleton, Next.js skeleton with mock/http API client, `@krama/contracts-ts` stub.

**Still open from F1 (Nachiketha, repo owner):**
- [x] Run the README quick start on his laptop (the F1 exit gate)
- [x] Apply [`setup/github-settings.md`](../setup/github-settings.md): rebase-only merges, ruleset on `main`, required checks, Maintain role for Vishwas

---

## Sprint F2: contracts v1

### Research before starting

> **Research chat prompts:** copy yours from [#10 (Vishwas)](https://github.com/NachikethaKG/Krama/issues/10) or [#11 (Nachiketha)](https://github.com/NachikethaKG/Krama/issues/11), or run `just research-prompt f <name>`. Together questions: [#12](https://github.com/NachikethaKG/Krama/issues/12). How it works: [`docs/research/`](../research/README.md).

**Vishwas**
- **Pydantic generation:** how does `datamodel-code-generator` turn JSON Schema (draft 2020-12) into Pydantic v2 models? Which flags give clean output (`--output-model-type pydantic_v2.BaseModel`, `--use-annotated`, enums as `Literal`)? Does it handle `$ref` across files?
- **OpenAPI from FastAPI:** how do you export `app.openapi()` to a file in a script? How do we make route response models *be* the generated models, so the OpenAPI output and the schemas can't drift?
- **Python Protocols:** `typing.Protocol` vs `abc.ABC` for the `ports/` interfaces. How does strict mypy check that a class satisfies a Protocol?

**Nachiketha**
- **TypeScript generation:** compare `json-schema-to-typescript`, `quicktype` and `openapi-typescript`. Which handles `$ref` across files and `oneOf` (for event types) best?
- **Fixture validation in JS:** how do you validate JSON fixtures against a schema with `ajv` (draft 2020-12 needs `ajv/dist/2020`)?
- **Mocking SSE in the browser:** how can `MockApiClient` replay a recorded event stream with real timings? (`EventSource` can't be pointed at a fake, so: a small async generator or a mock `EventSource` class?)

**Together**
- Do "create a repository" in local Gitea (http://localhost:3001, user `demo`) **by hand**. Write down every step: what you click, the URL after, the heading you see. That list becomes the first fixture and its `expected_state`s.
- Agree on naming: `snake_case` JSON, ids as UUID strings, timestamps as ISO-8601 UTC.

### Tasks

| Vishwas | Nachiketha |
|---|---|
| `contracts/schemas/` for `task`, `plan`, `run`, `events` | `contracts/schemas/` for `workflow`, `step` |
| `scripts/gen-contracts`: Python side (schemas → `backend/app/contracts_gen/`) | `scripts/gen-contracts`: TS side (schemas → `packages/contracts-ts/`) |
| `scripts/export-openapi` + `contracts/openapi.json` | Fixtures: the hand-captured Gitea "create repo" workflow + event stream (`contracts/fixtures/`) |
| CI job `contracts-drift` (regenerate + `git diff --exit-code`) | Test that validates every fixture against its schema (ajv) |
| Backend imports a generated model in `/health` | Frontend `lib/api.ts` uses generated types; `MockApiClient` serves the fixtures |

**Together (contract PR, both approve):** `backend/app/ports/` v1:
- `Observer`: `capture(page, step) -> ObservedState`, `start_recording(page)`, `stop_recording() -> RecordingRef`
- `Policy`: `assess_plan(plan) -> RiskReport`, `check_action(step, page_state) -> Decision` (allow / pause / stop), `mask(observed_state) -> ObservedState`
- one fake implementation of each in `ports/fakes.py`, so both sides can test without the other

### Exit criteria
- `just check` and CI green, including `contracts-drift`.
- Generated Pydantic and TS types compile, and **both** halves import them.
- Every fixture validates against its schema.
- Demoed on Nachiketha's laptop from a fresh pull.
