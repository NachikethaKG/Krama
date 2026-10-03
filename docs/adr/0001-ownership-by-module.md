# 0001 — Ownership by module, not by frontend/backend

- **Status:** accepted
- **Deciders:** Vishwas, Nachiketha
- **Issue:** #4

## Context
The first plan copied the PRD's split: Vishwas = everything backend/agent, Nachiketha = everything frontend.
That split was not driven by hardware: nothing in Krama needs a GPU (the LLM is Gemini in the cloud and Chromium runs headless on CPU), so Nachiketha's 16GB CPU-only laptop runs every backend module.
A pure frontend role would teach Nachiketha much less and make the backend a single point of knowledge.

## Decision
Ownership is by **module**. Each backend module is a folder owned by one person, so files still never overlap.

| Owner | Modules |
|---|---|
| Vishwas | `backend/app/{agent,planner,verifier,runs,api,db,llm,storage,tts}`, `backend/alembic/`, `backend/justfile` |
| Nachiketha | `backend/app/{observer,policy,validation,export}`, `benchmarks/` (harness + reports), `frontend/`, `packages/` |
| Both (contract) | `contracts/`, **`backend/app/ports/`**: the Python `Protocol` interfaces between backend modules owned by different people |
| Both (shared) | `backend/pyproject.toml`, `backend/uv.lock`, `benchmarks/tasks/` |

Rules that come with it:
- Cross-owner backend calls go **only through `backend/app/ports/`**. For example, the agent loop (Vishwas) calls `Observer` and `Policy` protocols and never imports `observer/` or `policy/` internals. Changing a port follows the contract-change protocol.
- Tests live in `backend/tests/<module>/`, owned with the module.
- Backend dependency changes (`pyproject.toml` / `uv.lock`) go in a tiny separate `build(deps)` PR, reviewed by the other person. If `uv.lock` conflicts, run `uv lock` again; never hand-merge it.

## Alternatives considered
- **Keep the frontend/backend split.** Simplest, but rejected for the reasons in Context.
- **Rotate ownership each phase.** Good for learning, but every rotation reshuffles CODEOWNERS and agent deny lists, and module knowledge never deepens. Rejected; `good-first-cross` issues cover rotation instead.
- **Shared ownership of the whole backend.** Rejected: two AI agents editing the same files is exactly the merge-conflict source we designed against.

## Consequences
- Nachiketha owns the product's safety layer (policy), its recording layer (observer) and its measurement (benchmarks, validation). These are core to "verified" tutorials, not side work.
- The interfaces in `ports/` must be written before either side implements them (Sprint F2).
- `OWNERSHIP.toml`, `CODEOWNERS`, `AGENTS.md` and the agent deny lists are updated to match.
