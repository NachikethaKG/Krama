"""Validation ports (#358): value types and the fake backend that #110/#111 are tested against."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.ports import ReplayOutcome, StepEvidence, ValidationRecord, WorkflowCandidate
from app.ports.fakes import FakeValidationBackend

pytestmark = pytest.mark.anyio


def candidate(**kw: object) -> WorkflowCandidate:
    data: dict[str, object] = {
        "workflow_id": uuid4(),
        "site": "127.0.0.1:3001",
        "target_app": "gitea",
        "status": "verified",
        "revision": 1,
    }
    return WorkflowCandidate.model_validate({**data, **kw})


def test_a_candidate_carries_its_recent_validations_newest_first() -> None:
    c = candidate(last_validated_at=datetime(2026, 11, 1, tzinfo=UTC), recent=["blocked", "passed"])

    assert c.recent == ("blocked", "passed")
    with pytest.raises(ValidationError):
        candidate(recent=["fine"])  # not a ValidationStatus


def test_replay_outcomes_are_one_of_three_results() -> None:
    failed = ReplayOutcome(
        result="failed",
        run_id=uuid4(),
        reason="locator_miss",
        step_seq=3,
        details={"candidates": [{"role": "button", "name": "Make repo"}]},
        steps=[StepEvidence(seq=1, stored_screenshot="runs/a/1.png", new_screenshot="runs/b/1.png")],
    )

    assert failed.steps[0].new_bbox is None and ReplayOutcome(result="refused").details == {}
    with pytest.raises(ValidationError):
        ReplayOutcome(result="skipped")
    with pytest.raises(ValidationError):
        ReplayOutcome(result="verified", new_version="superseded")


def test_a_validation_record_uses_the_contracts_statuses() -> None:
    record = ValidationRecord(workflow_id=uuid4(), status="heal_pending", drift_details={"reason": "x"})

    assert record.status == "heal_pending"
    with pytest.raises(ValidationError):
        ValidationRecord(workflow_id=uuid4(), status="drifted")


async def test_the_fake_backend_replays_scripted_outcomes_then_verifies() -> None:
    c = candidate()
    failed = ReplayOutcome(result="failed", reason="state_mismatch")
    backend = FakeValidationBackend([c], {c.workflow_id: [failed]})

    assert await backend.candidates() == [c]
    assert (await backend.replay(c.workflow_id)).reason == "state_mismatch"
    assert (await backend.replay(c.workflow_id)).result == "verified"  # nothing scripted any more
    await backend.record(ValidationRecord(workflow_id=c.workflow_id, status="outdated"))

    assert backend.replayed == [c.workflow_id, c.workflow_id] and backend.records[0].status == "outdated"
    with pytest.raises(LookupError):
        await backend.replay(uuid4())
