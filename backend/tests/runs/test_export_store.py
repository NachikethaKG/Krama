"""DbExportStore (#124): the export job's view of the `exports` table, through the ExportStore port."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db import ExportRow, WorkflowRow, WorkflowStepRow
from app.db.repositories import add_workflow_version
from app.ports import ExportNotFoundError, ExportStateError
from app.ports.models import ArtifactRef
from app.runs.exports import DbExportStore
from tests.api.test_exports import stored_workflow
from tests.api.test_flow import Sessions, make_user

pytestmark = pytest.mark.anyio

VIDEO = ArtifactRef(key="exports/x.mp4", content_type="video/mp4", size_bytes=4096)


async def new_export(sessions: Sessions, *, status: str = "queued") -> tuple[UUID, UUID]:
    user = await make_user(sessions)
    workflow_id = await stored_workflow(sessions, user)
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None and workflow.current_version_id is not None
        row = ExportRow(
            workflow_id=workflow_id,
            version_id=workflow.current_version_id,
            user_id=user.id,
            preset="landscape",
            voice="en_US-ljspeech-medium",
            status=status,
        )
        s.add(row)
        await s.flush()
        return row.id, workflow_id


async def row(sessions: Sessions, export_id: UUID) -> ExportRow:
    async with sessions() as s:
        found = await s.scalar(select(ExportRow).where(ExportRow.id == export_id))
        assert found is not None
        return found


async def test_load_gives_the_export_and_its_workflow(sessions: Sessions) -> None:
    export_id, workflow_id = await new_export(sessions)

    job = await DbExportStore(sessions).load(export_id)

    assert job.export.id == export_id and job.export.status == "queued" and job.export.revision == 1
    assert job.workflow.id == workflow_id and job.workflow.revision == 1
    assert len(job.workflow.steps) >= 1 and job.workflow.recording_path is not None


async def test_load_renders_the_exported_version_after_a_newer_one(sessions: Sessions) -> None:
    export_id, workflow_id = await new_export(sessions)
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None
        old_steps = (await s.scalars(select(WorkflowStepRow).where(WorkflowStepRow.workflow_id == workflow_id))).all()
        copy = [WorkflowStepRow(**{c: getattr(st, c) for c in ("seq", "action", "target", "expected_state",
                "observed_state", "verification", "risk")}, instruction_text="New wording")  # fmt: skip
                for st in old_steps]  # fmt: skip
        await add_workflow_version(
            s, workflow, copy, source="heal", status="current", run_id=None, confidence=0.9,
            recording_path="runs/new/rrweb_recording.json", viewport=None, change_summary=None,
        )  # fmt: skip

    job = await DbExportStore(sessions).load(export_id)

    assert job.workflow.revision == 1 and job.export.revision == 1
    assert "New wording" not in [st.instruction_text for st in job.workflow.steps]
    assert job.workflow.recording_path != "runs/new/rrweb_recording.json"


async def test_rendering_progress_then_ready(sessions: Sessions) -> None:
    export_id, _ = await new_export(sessions)
    store = DbExportStore(sessions)

    await store.mark_rendering(export_id, 0)
    await store.mark_rendering(export_id, 70)
    await store.mark_rendering(export_id, 20)  # progress never goes down
    await store.mark_rendering(export_id, 150)  # capped below 100 until ready
    mid = await row(sessions, export_id)
    await store.mark_ready(export_id, video=VIDEO, captions=None, duration_ms=31_000)
    done = await row(sessions, export_id)

    assert (mid.status, mid.progress) == ("rendering", 99) and mid.started_at is not None
    assert (done.status, done.progress, done.video_key, done.size_bytes) == ("ready", 100, VIDEO.key, 4096)
    assert done.finished_at is not None and done.started_at == mid.started_at


async def test_failed_keeps_a_short_message(sessions: Sessions) -> None:
    export_id, _ = await new_export(sessions)
    await DbExportStore(sessions).mark_failed(export_id, "narration_failed", "x" * 2000)
    failed = await row(sessions, export_id)
    assert (failed.status, failed.error_code, len(failed.error_message or "")) == ("failed", "narration_failed", 500)


@pytest.mark.parametrize("status", ["ready", "failed", "expired"])
async def test_finished_exports_never_change(sessions: Sessions, status: str) -> None:
    export_id, _ = await new_export(sessions, status=status)
    store = DbExportStore(sessions)
    with pytest.raises(ExportStateError):
        await store.mark_rendering(export_id, 10)
    with pytest.raises(ExportStateError):
        await store.mark_failed(export_id, "interrupted", "restart")
    with pytest.raises(ExportStateError, match=status):
        await store.mark_ready(export_id, video=VIDEO, captions=None, duration_ms=1)


async def test_ready_needs_rendering(sessions: Sessions) -> None:
    export_id, _ = await new_export(sessions)
    with pytest.raises(ExportStateError, match="queued"):
        await DbExportStore(sessions).mark_ready(export_id, video=VIDEO, captions=None, duration_ms=1)


async def test_unknown_export(sessions: Sessions) -> None:
    store = DbExportStore(sessions)
    with pytest.raises(ExportNotFoundError):
        await store.load(uuid4())
    with pytest.raises(ExportNotFoundError):
        await store.mark_failed(uuid4(), "internal", "x")
