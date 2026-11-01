"""Export cleanup (#125): retention, failed and orphan files, the disk cap order, busy files, dry runs and
narration clips. Real Postgres, real LocalFsStore under tmp_path."""

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db import ExportRow, WorkflowRow, WorkflowStepRow
from app.db.repositories import add_workflow_version
from app.storage import LocalFsStore
from app.storage.cleanup import CleanupReport, cleanup
from app.worker import export_cleanup_job, worker_settings
from tests.api.test_exports import stored_workflow
from tests.api.test_flow import Sessions, make_user

pytestmark = pytest.mark.anyio

NOW = datetime.now(UTC)
DAY = timedelta(days=1)
RETENTION = 30 * DAY
NO_CAP = 10**12


class World:
    def __init__(self, sessions: Sessions, tmp_path: Path) -> None:
        self.sessions = sessions
        self.root = tmp_path / "artifacts"
        self.files = LocalFsStore(self.root)

    async def workflow(self) -> tuple[UUID, UUID]:
        """A stored workflow and its current version."""
        workflow_id = await stored_workflow(self.sessions, await make_user(self.sessions))
        async with self.sessions() as s:
            workflow = await s.get(WorkflowRow, workflow_id)
            assert workflow is not None and workflow.current_version_id is not None
            return workflow_id, workflow.current_version_id

    async def export(
        self,
        workflow: tuple[UUID, UUID],
        *,
        status: str = "ready",
        age_days: float = 0,
        preset: str = "landscape",
        size: int = 1000,
        captions: bool = False,
    ) -> UUID:
        finished = NOW - timedelta(days=age_days)
        async with self.sessions.begin() as s:
            row = ExportRow(
                workflow_id=workflow[0],
                version_id=workflow[1],
                preset=preset,
                voice="v",
                status=status,
                progress=100 if status == "ready" else 0,
                finished_at=finished if status in ("ready", "failed") else None,
            )
            s.add(row)
            await s.flush()
            export_id = row.id
            if status in ("ready", "failed"):
                self.file(f"exports/{export_id}.mp4", size, age_days)
                if captions:
                    self.file(f"exports/{export_id}.vtt", 10, age_days)
            if status == "ready":
                row.video_key = f"exports/{export_id}.mp4"
                row.captions_key = f"exports/{export_id}.vtt" if captions else None
                row.size_bytes = size
        return export_id

    def file(self, key: str, size: int, age_days: float) -> Path:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * size)
        t = (NOW - timedelta(days=age_days)).timestamp()
        os.utime(path, (t, t))
        return path

    async def status(self, export_id: UUID) -> str:
        async with self.sessions() as s:
            row = await s.scalar(select(ExportRow).where(ExportRow.id == export_id))
            assert row is not None
            return row.status

    async def run(self, max_bytes: int = NO_CAP, dry_run: bool = False) -> CleanupReport:
        return await cleanup(
            self.sessions, self.files, now=NOW, retention=RETENTION, max_bytes=max_bytes, dry_run=dry_run
        )


@pytest.fixture
def world(sessions: Sessions, tmp_path: Path) -> World:
    return World(sessions, tmp_path)


async def test_old_exports_expire_but_the_newest_per_version_and_preset_stays(world: World) -> None:
    wf = await world.workflow()
    oldest = await world.export(wf, age_days=50, captions=True)
    newest_but_old = await world.export(wf, age_days=40)
    other_preset_old = await world.export(wf, age_days=45, preset="portrait")
    recent = await world.export(await world.workflow(), age_days=1)
    queued = await world.export(wf, status="queued")

    report = await world.run()

    assert await world.status(oldest) == "expired"
    assert not (world.root / f"exports/{oldest}.mp4").exists()
    assert not (world.root / f"exports/{oldest}.vtt").exists()
    for kept in (newest_but_old, other_preset_old, recent):  # protected or young
        assert await world.status(kept) == "ready"
        assert (world.root / f"exports/{kept}.mp4").exists()
    assert await world.status(queued) == "queued"
    assert report.expired == [oldest] and report.bytes_freed == 1010
    async with world.sessions() as s:
        row = await s.get(ExportRow, oldest)
        assert row is not None and row.video_key is None and row.captions_key is None


async def test_failed_exports_lose_their_partial_files_at_once(world: World) -> None:
    failed = await world.export(await world.workflow(), status="failed", age_days=0)
    await world.run()
    assert not (world.root / f"exports/{failed}.mp4").exists()
    assert await world.status(failed) == "failed"


async def test_files_nobody_knows_go_after_a_day(world: World) -> None:
    world.file("exports/stray-old.mp4", 5, age_days=2)
    world.file("exports/stray-new.mp4", 5, age_days=0.5)
    await world.run()
    assert not (world.root / "exports/stray-old.mp4").exists()
    assert (world.root / "exports/stray-new.mp4").exists()


async def test_the_cap_takes_unprotected_then_superseded_then_current(world: World) -> None:
    wf = await world.workflow()
    unprotected = await world.export(wf, age_days=5, size=1000)
    current_protected = await world.export(wf, age_days=3, size=1000)
    # a second workflow whose exported version gets superseded by a newer one
    wf2 = await world.workflow()
    superseded_protected = await world.export(wf2, age_days=1, size=1000)
    async with world.sessions.begin() as s:
        workflow = await s.get(WorkflowRow, wf2[0])
        assert workflow is not None
        steps = (await s.scalars(select(WorkflowStepRow).where(WorkflowStepRow.workflow_id == wf2[0]))).all()
        fields = ("seq", "action", "target", "instruction_text", "expected_state", "observed_state",
                  "verification", "risk")  # fmt: skip
        copy = [WorkflowStepRow(**{c: getattr(st, c) for c in fields}) for st in steps]
        await add_workflow_version(
            s, workflow, copy, source="heal", status="current", run_id=None, confidence=None,
            recording_path=None, viewport=None, change_summary=None,
        )  # fmt: skip

    report = await world.run(max_bytes=1500)

    # 3000 bytes > 1500: first the unprotected one, then the protected export of a superseded version.
    assert report.expired_over_cap == [unprotected, superseded_protected]
    assert await world.status(current_protected) == "ready"
    assert report.bytes_after == 1000


async def test_a_busy_file_is_kept_for_next_time(world: World) -> None:
    wf = await world.workflow()
    busy = await world.export(wf, age_days=60)
    other = await world.export(wf, age_days=50)
    await world.export(wf, age_days=1)  # the newest: both older ones are unprotected

    real_delete = world.files.delete

    async def delete(key: str) -> bool:
        if key == f"exports/{busy}.mp4":
            raise PermissionError("in use")
        return await real_delete(key)

    world.files.delete = delete  # type: ignore[method-assign]
    report = await world.run()

    assert await world.status(busy) == "ready"  # nothing half-done: the row still points at its file
    assert report.busy == [f"exports/{busy}.mp4"]
    assert report.expired == [other]  # the rest of the run went on


async def test_dry_run_changes_nothing(world: World) -> None:
    wf = await world.workflow()
    old = await world.export(wf, age_days=50)
    await world.export(wf, age_days=40)

    report = await world.run(dry_run=True)

    assert report.dry_run and report.expired == [old]
    assert await world.status(old) == "ready"
    assert (world.root / f"exports/{old}.mp4").exists()


async def test_only_unused_old_clips_go(world: World) -> None:
    await world.workflow()
    async with world.sessions() as s:
        live_text = await s.scalar(select(WorkflowStepRow.instruction_text).limit(1))
    assert live_text is not None
    live = hashlib.sha256(live_text.encode("utf-8")).hexdigest()
    dead = hashlib.sha256(b"Click the old button.").hexdigest()
    young = hashlib.sha256(b"Click the new button.").hexdigest()
    for sha, age in ((live, 90), (dead, 90), (young, 2)):
        world.file(f"narration/v/{sha}.wav", 100, age)
        world.file(f"narration/v/{sha}.json", 10, age)

    await world.run()

    assert (world.root / f"narration/v/{live}.wav").exists()
    assert not (world.root / f"narration/v/{dead}.wav").exists()
    assert not (world.root / f"narration/v/{dead}.json").exists()
    assert (world.root / f"narration/v/{young}.wav").exists()


async def test_the_worker_runs_cleanup_daily(world: World) -> None:
    settings = Settings(artifacts_dir=world.root, exports_retention_days=30)
    [job] = worker_settings(settings)["cron_jobs"]
    assert (job.hour, job.minute) == (3, 30)

    old_wf = await world.workflow()
    old = await world.export(old_wf, age_days=50)
    await world.export(old_wf, age_days=40)
    summary = await export_cleanup_job(
        {"settings": settings, "sessions": world.sessions, "files": world.files}
    )

    assert "1 export(s) expired" in summary
    assert await world.status(old) == "expired"
