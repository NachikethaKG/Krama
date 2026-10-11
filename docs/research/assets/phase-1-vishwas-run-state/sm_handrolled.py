"""Hand-rolled: a StrEnum + a transition table. Pure, typed, ~20 lines."""
from enum import StrEnum

class RunStatus(StrEnum):
    QUEUED = "queued"; RUNNING = "running"; PAUSED = "paused"
    VERIFIED = "verified"; FAILED = "failed"; CANCELLED = "cancelled"

S = RunStatus
ALLOWED: dict[RunStatus, frozenset[RunStatus]] = {
    S.QUEUED: frozenset({S.RUNNING, S.CANCELLED}),
    S.RUNNING: frozenset({S.PAUSED, S.VERIFIED, S.FAILED, S.CANCELLED}),
    S.PAUSED: frozenset({S.RUNNING, S.FAILED, S.CANCELLED}),
    S.VERIFIED: frozenset(), S.FAILED: frozenset(), S.CANCELLED: frozenset(),
}
TERMINAL = frozenset(s for s, nxt in ALLOWED.items() if not nxt)

class IllegalTransition(Exception):
    pass

def check(current: RunStatus, new: RunStatus) -> RunStatus:
    if new not in ALLOWED[current]:
        raise IllegalTransition(f"{current} -> {new}")
    return new

if __name__ == "__main__":
    s = check(S.QUEUED, S.RUNNING); s = check(s, S.PAUSED)
    try:
        check(s, S.VERIFIED)
    except IllegalTransition as e:
        print("illegal transition ->", e)
    print("terminal:", sorted(TERMINAL))
    # every status has an entry (exhaustive table)
    assert set(ALLOWED) == set(RunStatus)
    print("table covers all", len(RunStatus), "statuses")
