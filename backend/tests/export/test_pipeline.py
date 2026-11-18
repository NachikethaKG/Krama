"""The export pipeline around the job (#128 gate fixes).

D4 scene timing handed to the renderer, the outro's site and date, run_export's timeout / cancel / crash
handling, the in-process queue with recovery, the API using the real queue, the worker's export queue.
"""

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.api.services import Services
from app.config import Settings
from app.db import ExportRow, WorkflowRow
from app.export import EXPORT_JOB, EXPORT_QUEUE, InProcessExportQueue, run_export
from app.export.renderer import RenderResult
from app.ports.fakes import FakeExportStore
from app.storage import LocalFsStore
from app.worker import export_worker_settings
from tests.api.test_exports import ExportApi, stored_workflow
from tests.api.test_flow import Sessions, make_user
from tests.export.test_job import FakeNarrator, FakeVideoRenderer, make_test_export, make_test_workflow

pytestmark = pytest.mark.anyio


class SlowRenderer(FakeVideoRenderer):
    async def render(self, **kwargs: Any) -> RenderResult:
        await asyncio.sleep(30)
        return await super().render(**kwargs)


def fake_store(*, target_url: str | None = None) -> tuple[FakeExportStore, UUID]:
    export_id, workflow_id = uuid4(), uuid4()
    workflow = make_test_workflow(workflow_id)
    if target_url:
        workflow = workflow.model_copy(update={"target_url": target_url})
    store = FakeExportStore()
    store.add(make_test_export(export_id, workflow_id), workflow)
    return store, export_id


async def test_scenes_follow_the_narration_and_the_outro_names_the_site(tmp_path: Path) -> None:
    store, export_id = fake_store(target_url="https://github.com/krama-bench/x")
    renderer = FakeVideoRenderer()

    await run_export(
        export_id, store=store, files=LocalFsStore(tmp_path), narrator=FakeNarrator(), renderer=renderer,
        timeout_s=60,
    )  # fmt: skip

    [scene] = renderer.rendered_kwargs["scenes"]
    # step action 500 ms, clip 1200 ms: max(500, 300 + 1200 + 400) = 1900 ms = 57 frames
    assert (scene.step_seq, scene.frames, scene.duration_ms) == (1, 57, 1900)
    assert renderer.rendered_kwargs["site"] == "github.com"
    assert store.exports[export_id].status == "ready"


async def test_a_render_past_the_timeout_fails_as_timeout(tmp_path: Path) -> None:
    store, export_id = fake_store()
    status = await run_export(
        export_id,
        store=store,
        files=LocalFsStore(tmp_path),
        narrator=FakeNarrator(),
        renderer=SlowRenderer(),
        timeout_s=0.2,
    )
    failed = store.exports[export_id]
    assert status == "timeout" and failed.status == "failed"
    assert failed.error is not None and failed.error.code == "timeout"


async def test_a_cancelled_export_fails_as_interrupted(tmp_path: Path) -> None:
    store, export_id = fake_store()
    task = asyncio.create_task(
        run_export(
            export_id,
            store=store,
            files=LocalFsStore(tmp_path),
            narrator=FakeNarrator(),
            renderer=SlowRenderer(),
            timeout_s=60,
        )
    )
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    failed = store.exports[export_id]
    assert failed.status == "failed" and failed.error is not None and failed.error.code == "interrupted"


async def test_a_crash_never_leaves_the_export_rendering(tmp_path: Path) -> None:
    store, export_id = fake_store()
    real = store.mark_rendering
    calls = 0

    async def flaky(eid: UUID, progress: int) -> None:
        nonlocal calls
        calls += 1
        await real(eid, progress)
        if calls == 2:
            raise RuntimeError("database went away")

    store.mark_rendering = flaky  # type: ignore[method-assign,assignment]
    status = await run_export(
        export_id, store=store, files=LocalFsStore(tmp_path), narrator=FakeNarrator(),
        renderer=FakeVideoRenderer(), timeout_s=60,
    )  # fmt: skip
    failed = store.exports[export_id]
    assert status == "internal" and failed.error is not None and failed.error.code == "internal"


async def _export_row(sessions: Sessions, workflow_id: UUID, status: str) -> UUID:
    async with sessions.begin() as s:
        workflow = await s.get(WorkflowRow, workflow_id)
        assert workflow is not None and workflow.current_version_id is not None
        row = ExportRow(
            workflow_id=workflow_id, version_id=workflow.current_version_id, preset="landscape",
            voice="en_US-ljspeech-medium", status=status,
        )  # fmt: skip
        s.add(row)
        await s.flush()
        return row.id


async def _status(sessions: Sessions, export_id: UUID) -> tuple[str, str | None]:
    async with sessions() as s:
        row = await s.scalar(select(ExportRow).where(ExportRow.id == export_id))
        assert row is not None
        return row.status, row.error_code


def in_process(sessions: Sessions, tmp_path: Path) -> InProcessExportQueue:
    return InProcessExportQueue(
        sessions, LocalFsStore(tmp_path / "artifacts"), timeout_s=60,
        narrator=FakeNarrator, renderer=FakeVideoRenderer,
    )  # fmt: skip


async def test_in_process_queue_renders_and_recovers(sessions: Sessions, tmp_path: Path) -> None:
    workflow_id = await stored_workflow(sessions, await make_user(sessions))
    stale = await _export_row(sessions, workflow_id, "rendering")
    waiting = await _export_row(sessions, workflow_id, "queued")
    queue = in_process(sessions, tmp_path)

    await queue.recover()
    await queue.wait()

    assert await _status(sessions, stale) == ("failed", "interrupted")
    assert await _status(sessions, waiting) == ("ready", None)
    assert (tmp_path / "artifacts" / "exports" / f"{waiting}.mp4").is_file()


async def test_the_api_renders_through_the_real_queue(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path) as api:
        assert api.user is not None
        queue = in_process(sessions, tmp_path)
        api.svc.exports = queue
        api.app.dependency_overrides.clear()  # no mock queue: the composition root's queue
        workflow_id = await stored_workflow(sessions, api.user)
        created = await api.client.post(f"/workflows/{workflow_id}/exports", json={"preset": "portrait"})
        await queue.wait()
        polled = await api.client.get(f"/exports/{created.json()['id']}")

    assert created.status_code == 202
    assert polled.json()["status"] == "ready" and polled.json()["download_url"]


async def test_no_queue_is_a_clear_503(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path) as api:
        assert api.user is not None
        svc: Services = api.svc
        svc.exports = None
        api.app.dependency_overrides.clear()
        workflow_id = await stored_workflow(sessions, api.user)
        response = await api.client.post(f"/workflows/{workflow_id}/exports", json={"preset": "landscape"})
    assert response.status_code == 503


def test_the_worker_has_an_export_queue_one_at_a_time() -> None:
    config = export_worker_settings(Settings(export_timeout_seconds=900))
    [job] = config["functions"]
    assert (config["queue_name"], config["max_jobs"]) == (EXPORT_QUEUE, 1)
    assert (job.name, job.max_tries, job.timeout_s) == (EXPORT_JOB, 1, 1020)
