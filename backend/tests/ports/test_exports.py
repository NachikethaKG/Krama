"""Export contract and ports (Phase 5, #354): fixtures, the fake export store's status rules, the fake queue,
and the ArtifactFiles operations of the fake artifact store."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.contracts_gen.export_schema import CreateExportRequest, Export
from app.contracts_gen.workflow_schema import Workflow
from app.ports import ExportNotFoundError, ExportStateError, InvalidArtifactKeyError
from app.ports.fakes import TINY_MP4, FakeArtifactStore, FakeExportQueue, FakeExportStore
from app.ports.models import ArtifactNotFoundError, ArtifactRef

pytestmark = pytest.mark.anyio

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"
EXPORT_FIXTURES = sorted((CONTRACTS / "fixtures" / "exports").glob("*.json"))
WORKFLOW_FIXTURE = CONTRACTS / "fixtures" / "gitea-create-repo-workflow.json"
WORKFLOW = Workflow.model_validate_json(WORKFLOW_FIXTURE.read_bytes())


def new_export(**kw: object) -> Export:
    data: dict[str, object] = {
        "id": str(uuid4()),
        "workflow_id": str(WORKFLOW.id),
        "revision": 1,
        "preset": "landscape",
        "voice": "en_US-ljspeech-medium",
        "status": "queued",
        "progress": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return Export.model_validate({**data, **kw})


def store_with(export: Export) -> FakeExportStore:
    store = FakeExportStore()
    store.add(export, WORKFLOW)
    return store


# --- contract ---


@pytest.mark.parametrize("path", EXPORT_FIXTURES, ids=lambda p: p.name)
def test_export_fixtures_parse(path: Path) -> None:
    export = Export.model_validate(json.loads(path.read_text("utf-8")))
    assert (export.status == "ready") == (export.download_url is not None)
    assert (export.status == "failed") == (export.error is not None)


def test_every_status_has_a_fixture() -> None:
    statuses = {json.loads(p.read_text("utf-8"))["status"] for p in EXPORT_FIXTURES}
    assert statuses == {"queued", "rendering", "ready", "failed", "expired"}


@pytest.mark.parametrize("body", [{"preset": "square"}, {}, {"preset": "landscape", "voice": "x"}])
def test_create_request_takes_only_a_known_preset(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CreateExportRequest.model_validate(body)


def test_tiny_mp4_fixture_is_an_mp4() -> None:
    data = TINY_MP4.read_bytes()
    assert data[4:8] == b"ftyp" and len(data) < 10_000


# --- FakeExportStore ---


async def test_happy_path_queued_rendering_ready() -> None:
    export = new_export()
    store = store_with(export)
    video = ArtifactRef(key=f"exports/{export.id}.mp4", content_type="video/mp4", size_bytes=1234)

    await store.mark_rendering(export.id, 0)
    await store.mark_rendering(export.id, 60)
    await store.mark_rendering(export.id, 30)  # never goes down
    assert store.exports[export.id].progress == 60
    await store.mark_ready(export.id, video=video, captions=None, duration_ms=31_000)

    done = store.exports[export.id]
    assert (done.status, done.progress, done.size_bytes, done.duration_ms) == ("ready", 100, 1234, 31_000)
    assert done.download_url == f"/api/v1/exports/{export.id}/download"
    assert done.captions_url is None
    assert done.started_at is not None and done.finished_at is not None
    loaded = await store.load(export.id)
    assert loaded.workflow.id == WORKFLOW.id


async def test_failed_keeps_its_error() -> None:
    export = new_export()
    store = store_with(export)
    await store.mark_failed(export.id, "interrupted", "The worker restarted during the render.")
    failed = store.exports[export.id]
    assert failed.status == "failed" and failed.error is not None and failed.error.code == "interrupted"


@pytest.mark.parametrize("status", ["ready", "failed", "expired"])
async def test_finished_exports_dont_change(status: str) -> None:
    export = new_export(status=status)
    store = store_with(export)
    video = ArtifactRef(key="exports/x.mp4", content_type="video/mp4", size_bytes=1)
    with pytest.raises(ExportStateError):
        await store.mark_rendering(export.id, 10)
    with pytest.raises(ExportStateError):
        await store.mark_failed(export.id, "internal", "x")
    with pytest.raises(ExportStateError):
        await store.mark_ready(export.id, video=video, captions=None, duration_ms=1)


async def test_ready_needs_rendering_first() -> None:
    export = new_export()
    video = ArtifactRef(key="exports/x.mp4", content_type="video/mp4", size_bytes=1)
    with pytest.raises(ExportStateError, match="not rendering"):
        await store_with(export).mark_ready(export.id, video=video, captions=None, duration_ms=1)


async def test_unknown_export() -> None:
    with pytest.raises(ExportNotFoundError):
        await FakeExportStore().mark_rendering(UUID(int=1), 0)


# --- FakeExportQueue ---


async def test_queue_alone_only_records() -> None:
    queue = FakeExportQueue()
    await queue.enqueue(UUID(int=7))
    assert queue.enqueued == [UUID(int=7)]


async def test_queue_with_store_finishes_with_the_fixture_mp4() -> None:
    export = new_export()
    store, files = store_with(export), FakeArtifactStore()

    await FakeExportQueue(store, files).enqueue(export.id)

    assert store.exports[export.id].status == "ready"
    stored = await files.get(f"exports/{export.id}.mp4")
    assert stored.ref.content_type == "video/mp4" and stored.data == TINY_MP4.read_bytes()


async def test_queue_can_fail() -> None:
    export = new_export()
    store = store_with(export)
    await FakeExportQueue(store, FakeArtifactStore(), fail="render_failed").enqueue(export.id)
    failed = store.exports[export.id]
    assert failed.status == "failed" and failed.error is not None and failed.error.code == "render_failed"


# --- ArtifactFiles on the fake store ---


async def test_put_file_local_path_delete(tmp_path: Path) -> None:
    files = FakeArtifactStore()
    source = tmp_path / "out.mp4"
    source.write_bytes(TINY_MP4.read_bytes())

    ref = await files.put_file("exports/a.mp4", source, "video/mp4")
    served = await files.local_path("exports/a.mp4")

    assert ref.size_bytes == source.stat().st_size
    assert served.read_bytes() == source.read_bytes() and served != source
    assert await files.delete("exports/a.mp4") is True
    assert await files.delete("exports/a.mp4") is False
    with pytest.raises(ArtifactNotFoundError):
        await files.local_path("exports/a.mp4")


async def test_list_by_folder_prefix() -> None:
    files = FakeArtifactStore()
    for key in ["exports/b.mp4", "exports/a.mp4", "exportsX/c.mp4", "narration/v/1.wav"]:
        await files.put(key, b"1234", "video/mp4")

    listed = await files.list("exports/")

    assert [i.key for i in listed] == ["exports/a.mp4", "exports/b.mp4"]
    assert all(i.size_bytes == 4 and i.modified_at.tzinfo is not None for i in listed)


@pytest.mark.parametrize("prefix", ["exports", "../", "/exports/", ""])
async def test_list_rejects_unsafe_prefixes(prefix: str) -> None:
    with pytest.raises(InvalidArtifactKeyError):
        await FakeArtifactStore().list(prefix)
