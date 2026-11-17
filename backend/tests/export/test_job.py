"""Unit tests for render_export and export_job (#126)."""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.contracts_gen.common_schema import Action, ExpectedState
from app.contracts_gen.export_schema import Export
from app.contracts_gen.step_schema import ObservedState, Step, StepTarget, StepVerification
from app.contracts_gen.workflow_schema import Workflow, WorkflowViewport
from app.export.job import export_job, render_export
from app.export.renderer import RenderError, RenderResult, VideoRenderer
from app.ports.fakes import FakeExportStore
from app.ports.narration import NarrationClip, NarrationError, NarrationLine, NarrationManifest
from app.storage import LocalFsStore

pytestmark = pytest.mark.anyio


class FakeNarrator:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.narrated: list[Sequence[NarrationLine]] = []

    async def narrate(self, lines: Sequence[NarrationLine]) -> NarrationManifest:
        self.narrated.append(lines)
        if self.fail:
            raise NarrationError("synthesis_failed", "Synthetic synthesis error")
        clips = tuple(
            NarrationClip(
                step_seq=line.step_seq,
                text_sha256="a" * 64,
                audio_key=f"narration/test/{line.step_seq}.wav",
                duration_ms=1200,
            )
            for line in lines
        )
        return NarrationManifest(voice="en_US-ljspeech-medium", sample_rate=22050, clips=clips)


class FakeVideoRenderer(VideoRenderer):
    def __init__(self, duration_ms: int = 5000, fail: bool = False, timeout: bool = False) -> None:
        self.duration_ms = duration_ms
        self.fail = fail
        self.timeout = timeout
        self.rendered_kwargs: dict[str, Any] = {}

    async def render(self, **kwargs: Any) -> RenderResult:
        self.rendered_kwargs = kwargs
        if self.timeout:
            raise TimeoutError("Render process timed out")
        if self.fail:
            raise RenderError("Render process crashed")

        on_progress = kwargs.get("on_progress")
        if on_progress:
            await on_progress(25)
            await on_progress(75)

        output_path: Path = kwargs["output_path"]
        await asyncio.to_thread(output_path.write_bytes, b"fake mp4 video content")

        vtt_path: Path | None = kwargs.get("vtt_path")
        if vtt_path:
            await asyncio.to_thread(
                vtt_path.write_text, "WEBVTT\n\n00:00.000 --> 00:02.000\nStep 1", encoding="utf-8"
            )

        return RenderResult(
            output_path=output_path,
            duration_ms=self.duration_ms,
            vtt_path=vtt_path,
        )


def make_test_workflow(workflow_id: UUID) -> Workflow:
    return Workflow(
        id=workflow_id,
        version="1.0",
        revision=1,
        title="Test Workflow",
        target_app="gitea",
        status="verified",
        viewport=WorkflowViewport(width=1280, height=800, device_scale_factor=1.0),
        recording_path="runs/test/recording.json",
        steps=[
            Step(
                id=uuid4(),
                seq=1,
                action=Action(type="click"),
                target=StepTarget(selector="#btn", name="Button"),
                instruction_text="Click the button",
                expected_state=ExpectedState(),
                observed_state=ObservedState(url="http://gitea", title="Home", headings=[]),
                verification=StepVerification(result="verified", method=["dom"], confidence=1.0),
                risk="low",
                start_ms=100,
                end_ms=600,
            )
        ],
    )


def make_test_export(
    export_id: UUID, workflow_id: UUID, *, status: str = "queued", progress: int = 0
) -> Export:
    return Export(
        id=export_id,
        workflow_id=workflow_id,
        revision=1,
        title="Test Workflow",
        preset="landscape",
        voice="en_US-ljspeech-medium",
        status=status,
        progress=progress,
        created_at=datetime.now(UTC),
    )


async def test_render_export_happy_path(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)
    narrator = FakeNarrator()
    renderer = FakeVideoRenderer(duration_ms=6200)

    res = await render_export(export_id, store=store, files=files, narrator=narrator, renderer=renderer)
    assert res == "ready"

    # Export status in store
    final_export = store.exports[export_id]
    assert final_export.status == "ready"
    assert final_export.progress == 100
    assert final_export.duration_ms == 6200
    assert final_export.download_url == f"/api/v1/exports/{export_id}/download"
    assert final_export.captions_url == f"/api/v1/exports/{export_id}/captions.vtt"

    # Stored artifacts
    assert await files.exists(f"exports/{export_id}.mp4")
    assert await files.exists(f"exports/{export_id}.vtt")


async def test_render_export_interrupted_if_already_rendering(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id, status="rendering", progress=25)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)

    res = await render_export(export_id, store=store, files=files, narrator=FakeNarrator())
    assert res == "interrupted"

    final_export = store.exports[export_id]
    assert final_export.status == "failed"
    assert final_export.error is not None
    assert final_export.error.code == "interrupted"


async def test_render_export_skipped_if_not_queued(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id, status="ready", progress=100)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)

    res = await render_export(export_id, store=store, files=files, narrator=FakeNarrator())
    assert res == "ready"


async def test_render_export_narration_failure(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)
    narrator = FakeNarrator(fail=True)

    res = await render_export(export_id, store=store, files=files, narrator=narrator)
    assert res == "narration_failed"

    final_export = store.exports[export_id]
    assert final_export.status == "failed"
    assert final_export.error is not None
    assert final_export.error.code == "narration_failed"


async def test_render_export_render_failure(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)
    narrator = FakeNarrator()
    renderer = FakeVideoRenderer(fail=True)

    res = await render_export(export_id, store=store, files=files, narrator=narrator, renderer=renderer)
    assert res == "render_failed"

    final_export = store.exports[export_id]
    assert final_export.status == "failed"
    assert final_export.error is not None
    assert final_export.error.code == "render_failed"


async def test_render_export_timeout(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)
    narrator = FakeNarrator()
    renderer = FakeVideoRenderer(timeout=True)

    res = await render_export(export_id, store=store, files=files, narrator=narrator, renderer=renderer)
    assert res == "timeout"

    final_export = store.exports[export_id]
    assert final_export.status == "failed"
    assert final_export.error is not None
    assert final_export.error.code == "timeout"


async def test_export_job_context(tmp_path: Path) -> None:
    export_id = uuid4()
    workflow_id = uuid4()
    workflow = make_test_workflow(workflow_id)
    export = make_test_export(export_id, workflow_id)

    store = FakeExportStore()
    store.add(export, workflow)
    files = LocalFsStore(tmp_path)
    narrator = FakeNarrator()
    renderer = FakeVideoRenderer()

    ctx = {
        "export_store": store,
        "files": files,
        "narrator": narrator,
        "video_renderer": renderer,
    }

    res = await export_job(ctx, str(export_id))
    assert res == "ready"
    assert store.exports[export_id].status == "ready"
