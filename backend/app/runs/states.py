"""The run state machine: a StrEnum plus a transition table.

Research: docs/research/phase-1-vishwas-run-state-machine.md.

The database enforces the same table: every transition is a conditional UPDATE whose allowed source statuses
come from `sources()` (app.db.repositories.transition_run), so Python and SQL can't drift apart.

    queued ──► running ──► verified
      │          │  ▲
      │          ▼  │ (confirm allow, #59)
      │        paused
      ▼          │
    failed / cancelled   (from queued, running or paused)
"""

from enum import StrEnum

from app.contracts_gen.run_schema import RunStatus as ContractRunStatus
from app.db.base import literal_values


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    VERIFIED = "verified"
    FAILED = "failed"
    CANCELLED = "cancelled"


_Q, _R, _P = RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.PAUSED
_V, _F, _C = RunStatus.VERIFIED, RunStatus.FAILED, RunStatus.CANCELLED
ALLOWED: dict[RunStatus, frozenset[RunStatus]] = {
    _Q: frozenset({_R, _F, _C}),
    _R: frozenset({_P, _V, _F, _C}),
    _P: frozenset({_R, _F, _C}),
    _V: frozenset(),
    _F: frozenset(),
    _C: frozenset(),
}
TERMINAL: frozenset[RunStatus] = frozenset(s for s, exits in ALLOWED.items() if not exits)
ACTIVE: frozenset[RunStatus] = frozenset(RunStatus) - TERMINAL

# A forgotten status, or a contract status we don't model, fails at import time instead of mid-run.
assert set(ALLOWED) == set(RunStatus), "every status needs a row in ALLOWED"
assert {s.value for s in RunStatus} == set(literal_values(ContractRunStatus)), "RunStatus != contract"


class IllegalTransitionError(ValueError):
    def __init__(self, current: RunStatus, new: RunStatus) -> None:
        super().__init__(f"a run can't go from {current} to {new}")
        self.current, self.new = current, new


def check(current: RunStatus, new: RunStatus) -> None:
    """Raise IllegalTransitionError unless `current → new` is in the table."""
    if new not in ALLOWED[current]:
        raise IllegalTransitionError(current, new)


def sources(new: RunStatus) -> frozenset[RunStatus]:
    """Every status a run may be in to move to `new` (the `allowed_from` of the conditional UPDATE)."""
    return frozenset(s for s, exits in ALLOWED.items() if new in exits)


def event_type(current: RunStatus, new: RunStatus) -> str:
    """The live-view event that announces `current → new` (docs/api-contract.md)."""
    check(current, new)
    if new is RunStatus.RUNNING:
        return "run.started" if current is RunStatus.QUEUED else "run.resumed"
    return {
        RunStatus.PAUSED: "run.paused",
        RunStatus.VERIFIED: "run.completed",
        RunStatus.FAILED: "run.failed",
        RunStatus.CANCELLED: "run.cancelled",
    }[new]
