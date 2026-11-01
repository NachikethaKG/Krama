"""The run engine's side of scheduled validation (#110): RunValidationBackend on the real database, executor
and Chromium, against the local test site."""

from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db import ValidationRow, WorkflowRow
from app.ports.validation import ValidationRecord
from app.runs import InProcessExecutor
from app.runs.validation_backend import RunValidationBackend
from app.storage import LocalFsStore
from app.targets import TargetSetup
from app.validation import ScheduledValidator
from tests.api.test_flow import Api, Sessions, reply, services
from tests.api.test_reverify import change_step, verified_workflow
from tests.runs.test_runner import GOOD_PLAN

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("stop_runs")]


class OpenLimits:
    async def allowed(self, site: str) -> bool:
        return True

    async def started(self, site: str) -> None:
        pass

    async def finished(self, site: str, *, blocked: bool) -> None:
        pass


def backend_of(api: Api) -> RunValidationBackend:
    assert isinstance(api.svc.executor, InProcessExecutor)  # validation replays in the worker's process
    return RunValidationBackend(api.svc.sessions, api.svc.executor, lambda _url: TargetSetup())


async def workflow_status(sessions: Sessions, workflow_id: UUID) -> str:
    async with sessions() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None
        return workflow.status


async def test_a_working_workflow_replays_verified_with_each_steps_evidence(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        backend = backend_of(api)

        [candidate] = await backend.candidates()
        outcome = await backend.replay(workflow_id)

    assert (candidate.workflow_id, candidate.target_app, candidate.last_validated_at) == (
        workflow_id,
        "gitea",
        None,
    )
    assert candidate.site == site.removeprefix("http://")
    assert outcome.result == "verified" and outcome.new_version is None and outcome.run_id is not None
    assert [s.seq for s in outcome.steps] == [1, 2, 3, 4]
    first = outcome.steps[0]
    assert (
        first.stored_screenshot and first.new_screenshot and first.stored_screenshot != first.new_screenshot
    )
    assert first.stored_bbox is not None and first.new_bbox is not None


async def test_a_broken_workflow_is_validated_outdated_with_the_miss_and_then_recovers(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 1, target={"role": "link", "name": "Add an item"})
        validator = ScheduledValidator(backend_of(api), OpenLimits())

        assert await validator.run_due() == 1

        async with sessions() as s:
            [row] = (
                await s.scalars(select(ValidationRow).where(ValidationRow.workflow_id == workflow_id))
            ).all()
        assert row.status == "outdated" and row.run_id is not None and row.version_id is not None
        details = row.drift_details or {}
        assert details["reason"] == "locator_miss" and details["step_seq"] == 1
        assert "New item" in {c["name"] for c in details["candidates"]}
        assert await workflow_status(sessions, workflow_id) == "outdated"

        # The page "works again": a passing validation makes the outdated workflow verified again.
        await backend_of(api).record(ValidationRecord(workflow_id=workflow_id, status="passed"))
        assert await workflow_status(sessions, workflow_id) == "verified"
        [candidate] = await backend_of(api).candidates()
        assert candidate.recent == ("passed", "outdated")


async def test_blocked_and_skipped_leave_the_workflow_as_it_is(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        for status in ("blocked", "skipped"):
            await backend_of(api).record(ValidationRecord(workflow_id=workflow_id, status=status))

        assert await workflow_status(sessions, workflow_id) == "verified"


async def test_an_unreplayable_workflow_is_refused_without_a_run(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        await change_step(sessions, workflow_id, 2, risk="high")

        outcome = await backend_of(api).replay(workflow_id)

    assert (outcome.result, outcome.reason, outcome.step_seq, outcome.run_id) == (
        "refused",
        "high_risk_step",
        2,
        None,
    )


async def test_an_unchanged_page_is_validated_passed_with_no_drift(
    sessions: Sessions, tmp_path: Path, site: str
) -> None:
    """#111 end to end: the real screenshots of the stored run and of the replay, read through the artifact
    store, show no visual change and no moved target on the static test site."""
    async with Api(services(sessions, tmp_path, reply(GOOD_PLAN))) as api:
        workflow_id = await verified_workflow(api, site)
        validator = ScheduledValidator(backend_of(api), OpenLimits(), artifacts=LocalFsStore(tmp_path))

        assert await validator.run_due() == 1

    async with sessions() as s:
        [row] = (await s.scalars(select(ValidationRow).where(ValidationRow.workflow_id == workflow_id))).all()
    details = row.drift_details or {}
    assert row.status == "passed" and (details["drift_class"], details["drift_reason"]) == (
        "ignore",
        "no change",
    )
    signals = details["signals"]
    assert [s["seq"] for s in signals] == [1, 2, 3, 4]
    assert all(s["visual_change"] < 0.05 and s.get("shift_px", 0) <= 30 for s in signals), signals
