# Run state machine and crash-safe state

- **Phase:** 1
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **State machines in Python:** the `transitions` library vs a hand-rolled enum + transition table. How do you persist state safely so a crash mid-run doesn't corrupt it?

## Findings
Experiments ran on 2026-10-11 against Postgres 16.15 from `infra/docker-compose.yml`, in a throwaway venv (nothing added to `backend/`). Scripts: [`assets/phase-1-vishwas-run-state/`](assets/phase-1-vishwas-run-state/)

**Statuses to model.** The contract's `RunStatus` is `queued|running|paused|verified|failed|cancelled` (`contracts/schemas/run.schema.json`, `docs/database-schema.md`). The phase file's `draft → approved` belong to the **plan** (`plans.status = proposed|approved|rejected`), not the run [verified locally: `app/contracts_gen/run_schema.py`].

**`transitions` 0.9.3** (MIT, depends on `six`) [verified locally: package metadata]
- `AsyncMachine` works: triggers become awaitable methods (`await run.start()`), `on_enter_<state>` callbacks run, and an illegal trigger raises `MachineError("Can't trigger event succeed from state paused!")` [verified locally: `sm_transitions.py`]
- Building one machine per run costs ~0.14 ms (1000 machines in 139 ms), so speed is not an issue [verified locally]
- **The methods and the `state` attribute are added at runtime, so mypy can't see them.** A 6-line probe gives `"Run" has no attribute "go"` and `"Run" has no attribute "state"` under `mypy --strict` [verified locally: `sm_mypy_probe.py`, mypy 2.4.0]. Our CI runs mypy on `backend/`, so every call would need a `type: ignore` or a hand-written stub.
- It holds the state in memory. Persisting is still our job, so the library doesn't help with the hard part of the question.

**Hand-rolled: `StrEnum` + transition table** [verified locally: `sm_handrolled.py`]
- ~20 lines: `ALLOWED: dict[RunStatus, frozenset[RunStatus]]`, a `check(current, new)` that raises `IllegalTransition`, and `TERMINAL` derived from the table (statuses with no exits: `verified`, `failed`, `cancelled`).
- An assert that the table covers every status catches a forgotten status at import time. `mypy --strict` is clean.

**Crash-safe persistence: the database is the state machine's memory**

Pattern tested: **one transaction per transition**, with a conditional UPDATE (compare-and-set) and the event in the same transaction:
```sql
UPDATE runs SET status = :new, last_event_seq = last_event_seq + 1
 WHERE id = :id AND status = ANY(:allowed_from)      -- the transition table, enforced by the DB
RETURNING last_event_seq;                            -- no row back = illegal or lost a race
INSERT INTO run_events (run_id, seq, type, data) VALUES (:id, <returned seq>, 'run.status', ...);
COMMIT;
```
Results (SQLAlchemy 2.1.4 async + asyncpg 0.32.0) [verified locally: `persist.py`]:
The experiment used a generic `run.status` event type; the real event types come from `docs/api-contract.md`.
1. **Crash before commit:** a child process ran the UPDATE + INSERT and then `os._exit(1)` before commit. Afterwards the run was still `queued`, with `last_event_seq = 0` and no event. Postgres rolls back the open transaction when the connection dies, so a crash can't leave a half-written transition.
2. **Illegal transition:** `verified → paused` matched no row and returned `None`. Nothing was written.
3. **Race:** 20 concurrent tasks tried `running → cancelled` and `running → verified` on the same run. **Exactly 1 won**, and it wrote exactly 1 event. The row lock taken by UPDATE serialises the others, and they then fail the `status = ANY(...)` check.
4. **Event numbering:** 200 concurrent event appends on one run gave seq **1..200 with no gaps and no primary-key clashes**. A `last_event_seq` counter on `runs`, bumped in the same UPDATE, is enough. `SELECT max(seq)+1` would race.

**What a crash still leaves behind.** A process that dies *between* transitions leaves the run at its last committed status, usually `running`, with no browser behind it. Nothing in the run itself can fix that, so the API needs a startup sweep: `UPDATE runs SET status='failed', error={code:'internal', message:'interrupted by restart'} WHERE status IN ('queued','running')`, plus a `run.failed` event. A browser session can't be resumed after a restart, so `failed` is the honest status. `paused` runs survive restarts as they are, because they're waiting on a human [unverified: design reasoning, not tested].

## Recommendation
Decisions (Vishwas, 2026-10-11):
- **Hand-rolled `StrEnum` + transition table** in `runs/`, not `transitions`. It is fully typed, has no dependency, and the library only covers the easy, in-memory half.
- **Every transition is one DB transaction:** a conditional UPDATE on `runs` (status ∈ allowed sources) **plus** the `run_events` row, with `seq` taken from `runs.last_event_seq`. The Python table and the SQL `allowed_from` come from the same `ALLOWED` dict, so they can't drift.
- Add a **CHECK constraint** on `runs.status` with the 6 values. Remember that Alembic autogenerate does **not** detect CHECK changes (see [phase-1-vishwas-database](phase-1-vishwas-database.md)).
- **Startup sweep:** on API start, move `queued`/`running` runs to `failed` ("interrupted by restart") and emit their final event.
- Schema impact: `runs` gains `last_event_seq int not null default 0`. This is a `docs/database-schema.md` change, so it goes through a small contract PR before the migration (#47).

## Open questions
- Should a sweep-failed run be retryable from the UI ("run again" creates a new run from the same approved plan)? This is UI and Nachiketha's call; the backend already allows it, because a new run is a new row.

## Links
- https://github.com/pytransitions/transitions (0.9.3)
- https://www.postgresql.org/docs/16/sql-update.html (UPDATE … RETURNING)
- https://www.postgresql.org/docs/16/explicit-locking.html (row-level locks)
