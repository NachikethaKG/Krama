"""Scheduled validation (#110): what is due, the confirm replay (D7), per-site limits, and what is recorded.
Against the fake ValidationBackend: no browser, no database."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.ports.fakes import FakeValidationBackend
from app.ports.validation import ReplayOutcome, WorkflowCandidate
from app.validation import ScheduledValidator
from app.validation.classify import classify
from app.validation.scheduler import due

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def candidate(
    ago: timedelta | None = None, recent: tuple[str, ...] = (), site: str = "127.0.0.1:3001"
) -> WorkflowCandidate:
    return WorkflowCandidate.model_validate(
        {
            "workflow_id": uuid4(),
            "site": site,
            "target_app": "gitea",
            "status": "verified",
            "revision": 1,
            "last_validated_at": NOW - ago if ago is not None else None,
            "recent": recent,
        }
    )


class MemoryLimits:
    def __init__(self, closed: set[str] | None = None) -> None:
        self.closed = closed or set()
        self.starts: list[str] = []
        self.ends: list[tuple[str, bool]] = []

    async def allowed(self, site: str) -> bool:
        return site not in self.closed

    async def started(self, site: str) -> None:
        self.starts.append(site)

    async def finished(self, site: str, *, blocked: bool) -> None:
        self.ends.append((site, blocked))


def validator(
    backend: FakeValidationBackend, limits: MemoryLimits | None = None, per_pass: int = 3
) -> ScheduledValidator:
    return ScheduledValidator(backend, limits or MemoryLimits(), per_pass=per_pass, now=lambda: NOW)


@pytest.mark.parametrize(
    ("ago", "recent", "is_due"),
    [
        (None, (), True),  # never checked
        (timedelta(days=6), ("passed",), False),
        (timedelta(days=7), ("passed",), True),
        (timedelta(minutes=50), ("blocked",), False),  # 1st blocked: 1 h back-off
        (timedelta(hours=1), ("blocked",), True),
        (timedelta(hours=3), ("blocked", "blocked"), False),  # 2nd: 4 h
        (timedelta(hours=23), ("blocked", "blocked", "blocked"), False),  # 3rd: 24 h
        (timedelta(days=2), ("blocked",) * 4, False),  # then the normal 7 days again
        (timedelta(days=7), ("blocked",) * 4, True),
        (timedelta(hours=2), ("blocked", "passed", "blocked"), True),  # only blocked in a row count
    ],
)
def test_what_is_due(ago: timedelta | None, recent: tuple[str, ...], is_due: bool) -> None:
    assert due(candidate(ago, recent), NOW) is is_due


async def test_a_pass_validates_only_due_workflows_within_the_per_pass_cap() -> None:
    fresh = candidate(timedelta(days=1), ("passed",))
    due_ones = [
        candidate(),
        candidate(timedelta(days=8), ("passed",)),
        candidate(timedelta(days=9), ("passed",)),
    ]
    backend = FakeValidationBackend([fresh, *due_ones])

    assert await validator(backend, per_pass=2).run_due() == 2
    assert backend.replayed == [due_ones[0].workflow_id, due_ones[1].workflow_id]
    assert [r.status for r in backend.records] == ["passed", "passed"]


async def test_a_closed_site_is_skipped() -> None:
    github = candidate(site="github.com")
    gitea = candidate()
    limits = MemoryLimits(closed={"github.com"})
    backend = FakeValidationBackend([github, gitea])

    assert await validator(backend, limits).run_due() == 1
    assert backend.replayed == [gitea.workflow_id] and limits.starts == ["127.0.0.1:3001"]


async def test_drift_that_repeats_marks_the_workflow_outdated_with_the_evidence() -> None:
    c = candidate()
    miss = ReplayOutcome(
        result="failed",
        reason="locator_miss",
        step_seq=3,
        run_id=uuid4(),
        details={"candidates": [{"role": "button", "name": "Make repo"}], "heal": {"reason": "best 0.6"}},
    )
    backend = FakeValidationBackend([c], {c.workflow_id: [miss, miss]})

    record = await validator(backend).validate(c)

    assert backend.replayed == [c.workflow_id] * 2  # the confirm replay (D7)
    assert record.status == "outdated" and record.run_id == miss.run_id
    assert record.drift_details["reason"] == "locator_miss" and record.drift_details["step_seq"] == 3
    assert record.drift_details["heal"] == {"reason": "best 0.6"} and "flake" not in record.drift_details


async def test_drift_that_doesnt_repeat_is_a_flake_and_changes_nothing() -> None:
    c = candidate()
    first = ReplayOutcome(result="failed", reason="state_mismatch", step_seq=2, run_id=uuid4())
    backend = FakeValidationBackend([c], {c.workflow_id: [first]})  # the second replay verifies

    record = await validator(backend).validate(c)

    assert record.status == "passed"
    assert record.drift_details["flake"] == {
        "reason": "state_mismatch",
        "step_seq": 2,
        "run_id": str(first.run_id),
    }


async def test_two_different_failures_are_blocked_not_outdated() -> None:
    c = candidate()
    first = ReplayOutcome(result="failed", reason="locator_miss", step_seq=1)
    second = ReplayOutcome(result="failed", reason="state_mismatch", step_seq=4)
    backend = FakeValidationBackend([c], {c.workflow_id: [first, second]})

    assert (await validator(backend).validate(c)).status == "blocked"


async def test_the_environment_is_never_replayed_twice_nor_outdated() -> None:
    c = candidate()
    limited = ReplayOutcome(result="failed", reason="rate_limited", step_seq=1)
    limits = MemoryLimits()
    backend = FakeValidationBackend([c], {c.workflow_id: [limited]})

    record = await validator(backend, limits).validate(c)

    assert backend.replayed == [c.workflow_id] and record.status == "blocked"
    assert limits.ends == [("127.0.0.1:3001", True)]  # a strike against the site


@pytest.mark.parametrize(
    ("outcome", "status"),
    [
        (ReplayOutcome(result="verified"), "passed"),
        (ReplayOutcome(result="verified", new_version="current"), "healed"),
        (ReplayOutcome(result="verified", new_version="pending_review"), "heal_pending"),
        (ReplayOutcome(result="failed", reason="locator_miss"), "outdated"),
        (ReplayOutcome(result="failed", reason="state_mismatch"), "outdated"),
        (ReplayOutcome(result="failed", reason="destructive_action"), "outdated"),
        (ReplayOutcome(result="failed", reason="captcha"), "blocked"),
        (ReplayOutcome(result="failed", reason="sign_in_required"), "blocked"),
        (ReplayOutcome(result="failed", reason="cancelled"), "blocked"),
        (ReplayOutcome(result="refused", reason="reset_failed"), "blocked"),
        (ReplayOutcome(result="refused", reason="high_risk_step"), "skipped"),
        (ReplayOutcome(result="refused", reason="secret_not_stored"), "skipped"),
    ],
)
def test_the_decided_outcome_table(outcome: ReplayOutcome, status: str) -> None:
    assert classify(outcome) == status
