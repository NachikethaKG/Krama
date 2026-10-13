import pytest

from app.contracts_gen.run_schema import RunStatus as ContractRunStatus
from app.db.base import literal_values
from app.runs.states import (
    ACTIVE,
    ALLOWED,
    TERMINAL,
    IllegalTransitionError,
    RunStatus,
    check,
    event_type,
    sources,
)

S = RunStatus


def test_statuses_are_exactly_the_contract_ones() -> None:
    assert {s.value for s in S} == set(literal_values(ContractRunStatus))
    assert set(ALLOWED) == set(S)


def test_terminal_statuses_have_no_exits() -> None:
    assert {S.VERIFIED, S.FAILED, S.CANCELLED} == TERMINAL
    assert {S.QUEUED, S.RUNNING, S.PAUSED} == ACTIVE


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.QUEUED, S.RUNNING),
        (S.QUEUED, S.CANCELLED),
        (S.RUNNING, S.PAUSED),
        (S.RUNNING, S.VERIFIED),
        (S.RUNNING, S.FAILED),
        (S.PAUSED, S.RUNNING),
        (S.PAUSED, S.CANCELLED),
    ],
)
def test_allowed_transitions(current: RunStatus, new: RunStatus) -> None:
    check(current, new)


@pytest.mark.parametrize(
    ("current", "new"),
    [
        (S.QUEUED, S.VERIFIED),  # can't verify without running
        (S.QUEUED, S.PAUSED),
        (S.PAUSED, S.VERIFIED),  # must resume first
        (S.VERIFIED, S.RUNNING),
        (S.FAILED, S.RUNNING),
        (S.CANCELLED, S.QUEUED),
        (S.RUNNING, S.RUNNING),
        (S.RUNNING, S.QUEUED),
    ],
)
def test_illegal_transitions_raise(current: RunStatus, new: RunStatus) -> None:
    with pytest.raises(IllegalTransitionError, match=f"from {current} to {new}"):
        check(current, new)


def test_sources_are_the_allowed_from_of_the_sql_update() -> None:
    assert sources(S.RUNNING) == {S.QUEUED, S.PAUSED}
    assert sources(S.CANCELLED) == {S.QUEUED, S.RUNNING, S.PAUSED}
    assert sources(S.VERIFIED) == {S.RUNNING}
    assert sources(S.QUEUED) == frozenset()


def test_every_transition_has_its_contract_event() -> None:
    assert event_type(S.QUEUED, S.RUNNING) == "run.started"
    assert event_type(S.PAUSED, S.RUNNING) == "run.resumed"
    assert event_type(S.RUNNING, S.PAUSED) == "run.paused"
    assert event_type(S.RUNNING, S.VERIFIED) == "run.completed"
    assert event_type(S.QUEUED, S.FAILED) == "run.failed"
    assert event_type(S.PAUSED, S.CANCELLED) == "run.cancelled"
    with pytest.raises(IllegalTransitionError):
        event_type(S.VERIFIED, S.FAILED)
