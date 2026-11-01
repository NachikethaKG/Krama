"""MP4 export API (#124): create (with re-use), status, download with Range, captions, ownership, and the
mock export queue that stands in for the export job until #126."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.api.exports import get_export_queue
from app.contracts_gen.export_schema import Export
from app.db import ExportRow, PlanRow, RunRow, TaskRow, UserRow, WorkflowRow, WorkflowStepRow
from app.db.repositories import add_workflow
from app.ports import ArtifactFiles, ExportQueue
from app.ports.fakes import TINY_MP4, FakeExportQueue
from app.runs.exports import DbExportStore
from app.storage import LocalFsStore, get_artifact_files
from tests.api.test_flow import Api, Sessions, make_user, services

pytestmark = pytest.mark.anyio

FIXTURE = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "gitea-create-repo-workflow.json"
STEP_FIELDS = ("seq", "action", "target", "instruction_text", "before_state", "expected_state", "observed_state",
               "verification", "risk", "sensitive", "screenshot_path", "start_ms", "end_ms")  # fmt: skip


async def stored_workflow(sessions: Sessions, user: UserRow, *, status: str = "verified") -> UUID:
    """A stored workflow owned by `user`, with the contract fixture's steps (no browser run needed)."""
    fixture = json.loads(FIXTURE.read_text("utf-8"))
    async with sessions.begin() as s:
        task = TaskRow(user_id=user.id, prompt="Create a repository", target_url="http://gitea", status="planned")
        s.add(task)
        await s.flush()
        plan = PlanRow(task_id=task.id, status="approved", risk="low", expected_result="repo", steps=[])
        s.add(plan)
        await s.flush()
        run = RunRow(plan_id=plan.id, plan_revision=1, status="verified")
        s.add(run)
        await s.flush()
        workflow = WorkflowRow(
            task_id=task.id,
            run_id=run.id,
            user_id=user.id,
            title="Create a repository in local Gitea",
            target_app="gitea",
            target_url="http://gitea",
            status=status,
            recording_path=f"runs/{run.id}/rrweb_recording.json",
            viewport={"width": 1280, "height": 800, "device_scale_factor": 1.0},
        )
        steps = [WorkflowStepRow(**{k: st.get(k) for k in STEP_FIELDS}) for st in fixture["steps"]]
        await add_workflow(s, workflow, steps)
        return workflow.id


class ExportApi(Api):
    """The app with a real LocalFsStore under tmp_path and a chosen export queue."""

    def __init__(self, sessions: Sessions, tmp_path: Path, queue: str = "mock", user: UserRow | None = None):
        super().__init__(services(sessions, tmp_path), user)
        self.files = LocalFsStore(tmp_path / "artifacts")
        self.recorder = FakeExportQueue()

        def pick_queue() -> ExportQueue:
            if queue == "record":
                return self.recorder
            return FakeExportQueue(DbExportStore(sessions), self.files, fail="render_failed" if queue == "fail" else None)

        def pick_files() -> ArtifactFiles:
            return self.files

        self.app.dependency_overrides[get_export_queue] = pick_queue
        self.app.dependency_overrides[get_artifact_files] = pick_files

    async def export(self, workflow_id: UUID, preset: str = "landscape") -> tuple[int, dict[str, Any]]:
        r = await self.client.post(f"/workflows/{workflow_id}/exports", json={"preset": preset})
        return r.status_code, r.json()


async def test_export_renders_with_the_mock_queue_and_downloads(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)

        status, body = await api.export(workflow_id)
        export = Export.model_validate(body)
        polled = Export.model_validate((await api.client.get(f"/exports/{export.id}")).json())
        download = await api.client.get(f"/exports/{export.id}/download")
        part = await api.client.get(f"/exports/{export.id}/download", headers={"Range": "bytes=0-99"})

    assert status == 202
    assert (export.status, export.revision, export.preset, export.voice) == (
        "queued", 1, "landscape", "en_US-ljspeech-medium")  # fmt: skip
    assert polled.status == "ready" and polled.progress == 100
    assert polled.download_url == f"/api/v1/exports/{export.id}/download" and polled.captions_url is None
    assert polled.size_bytes == TINY_MP4.stat().st_size and polled.duration_ms == 1000
    assert download.status_code == 200 and download.content == TINY_MP4.read_bytes()
    assert download.headers["content-type"] == "video/mp4"
    assert 'filename="create-a-repository-in-local-gitea-v1-landscape.mp4"' in download.headers["content-disposition"]
    assert part.status_code == 206 and len(part.content) == 100


async def test_same_version_and_preset_is_reused(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path, queue="record") as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)

        first = await api.export(workflow_id)
        again = await api.export(workflow_id)
        other_preset = await api.export(workflow_id, "portrait")

    assert (first[0], again[0], other_preset[0]) == (202, 200, 202)
    assert again[1]["id"] == first[1]["id"] and other_preset[1]["id"] != first[1]["id"]
    assert len(api.recorder.enqueued) == 2


async def test_a_failed_export_is_rendered_again(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path, queue="fail") as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        _, failed = await api.export(workflow_id)
        status = Export.model_validate((await api.client.get(f"/exports/{failed['id']}")).json())
        again = await api.export(workflow_id)
        not_ready = await api.client.get(f"/exports/{failed['id']}/download")

    assert status.status == "failed" and status.error is not None and status.error.code == "render_failed"
    assert again[0] == 202 and again[1]["id"] != failed["id"]
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["details"]["reason"] == "export_not_ready"


@pytest.mark.parametrize("status", ["outdated", "draft"])
async def test_only_verified_workflows_export(sessions: Sessions, tmp_path: Path, status: str) -> None:
    async with ExportApi(sessions, tmp_path, queue="record") as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user, status=status)
        code, body = await api.export(workflow_id)

    assert code == 409 and body["error"]["details"]["reason"] == "workflow_not_verified"
    assert api.recorder.enqueued == []


async def test_other_peoples_exports_are_404(sessions: Sessions, tmp_path: Path) -> None:
    owner = await make_user(sessions)
    workflow_id = await stored_workflow(sessions, owner)
    async with ExportApi(sessions, tmp_path, user=owner) as api:
        _, export = await api.export(workflow_id)
    async with ExportApi(sessions, tmp_path) as stranger:
        create = await stranger.export(workflow_id)
        get = await stranger.client.get(f"/exports/{export['id']}")
        download = await stranger.client.get(f"/exports/{export['id']}/download")
        unknown = await stranger.client.get(f"/exports/{uuid4()}")

    assert [create[0], get.status_code, download.status_code, unknown.status_code] == [404, 404, 404, 404]


async def test_unknown_preset_is_422(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path, queue="record") as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        code, _ = await api.export(workflow_id, "square")
    assert code == 422


async def test_captions_are_served_when_the_job_stored_them(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path, queue="record") as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        _, body = await api.export(workflow_id)
        export_id = UUID(body["id"])
        no_captions_yet = await api.client.get(f"/exports/{export_id}/captions.vtt")
        # What the export job (#126) does: store the files, then report through the ExportStore port.
        store = DbExportStore(sessions)
        vtt = tmp_path / "c.vtt"
        vtt.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nClick Create.\n", encoding="utf-8")
        await store.mark_rendering(export_id, 50)
        video = await api.files.put_file(f"exports/{export_id}.mp4", TINY_MP4, "video/mp4")
        captions = await api.files.put_file(f"exports/{export_id}.vtt", vtt, "text/vtt")
        await store.mark_ready(export_id, video=video, captions=captions, duration_ms=1000)
        ready = Export.model_validate((await api.client.get(f"/exports/{export_id}")).json())
        served = await api.client.get(f"/exports/{export_id}/captions.vtt")

    assert no_captions_yet.status_code == 404
    assert ready.captions_url == f"/api/v1/exports/{export_id}/captions.vtt"
    assert served.status_code == 200 and served.text.startswith("WEBVTT")
    assert served.headers["content-type"].startswith("text/vtt")


async def test_a_missing_file_is_404_not_500(sessions: Sessions, tmp_path: Path) -> None:
    async with ExportApi(sessions, tmp_path) as api:
        assert api.user is not None
        workflow_id = await stored_workflow(sessions, api.user)
        _, body = await api.export(workflow_id)
        await api.files.delete(f"exports/{body['id']}.mp4")
        response = await api.client.get(f"/exports/{body['id']}/download")
    assert response.status_code == 404


async def test_a_queue_error_fails_the_export(sessions: Sessions, tmp_path: Path) -> None:
    class Broken:
        async def enqueue(self, export_id: UUID) -> None:
            raise ConnectionError("redis down")

    async with ExportApi(sessions, tmp_path) as api:
        assert api.user is not None
        api.app.dependency_overrides[get_export_queue] = lambda: Broken()
        workflow_id = await stored_workflow(sessions, api.user)
        code, _ = await api.export(workflow_id)
    async with sessions() as s:
        [row] = (await s.scalars(select(ExportRow).where(ExportRow.workflow_id == workflow_id))).all()

    assert code == 503
    assert (row.status, row.error_code) == ("failed", "internal")
