"""Unit tests for Observer artifact persistence via ArtifactStore port."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import Page

from app.contracts_gen.common_schema import Action, Target
from app.observer import Observation, PageObserver, RRWebRecorder
from app.ports import ArtifactStore
from app.ports.fakes import FakeArtifactStore
from app.ports.models import ObservedState, StepRef
from app.storage.local import LocalFsStore


@pytest.fixture
def mock_artifact_store() -> MagicMock:
    """Mock ArtifactStore implementing save() as an AsyncMock."""
    store = MagicMock(spec=ArtifactStore)
    store.save = AsyncMock(side_effect=lambda key, data, content_type: f"stored/{key}")
    return store


@pytest.fixture
def sample_step() -> StepRef:
    return StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(selector="#refresh-btn"),
        instruction_text="Click refresh",
    )


@pytest.mark.anyio
async def test_capture_persists_screenshot_with_mock_store(
    mock_gitea_page: Page,
    mock_artifact_store: MagicMock,
    sample_step: StepRef,
) -> None:
    """Assert ArtifactStore.save is called with screenshot payload, key, and returned in observed_state."""
    await mock_gitea_page.goto("http://gitea.local/")
    observer = PageObserver(artifact_store=mock_artifact_store, run_id="run-42")

    observation = await observer.capture(mock_gitea_page, sample_step)

    # 1. Assert return model is an ObservedState and Observation
    assert isinstance(observation, ObservedState)
    assert isinstance(observation, Observation)

    # 2. Assert screenshot path matches the store.save return value
    expected_key = "runs/run-42/steps/1_screenshot.png"
    assert observation.screenshot_path == f"stored/{expected_key}"

    # 3. Assert mock ArtifactStore.save was called with correct parameters
    mock_artifact_store.save.assert_awaited_once()
    call_kwargs = mock_artifact_store.save.await_args.kwargs
    assert call_kwargs["key"] == expected_key
    assert call_kwargs["content_type"] == "image/png"
    assert isinstance(call_kwargs["data"], bytes)
    assert len(call_kwargs["data"]) > 0


@pytest.mark.anyio
async def test_capture_with_custom_step_id_and_screenshot_bytes(
    mock_artifact_store: MagicMock,
) -> None:
    """Assert capture with explicit step_id and bytes saves to ArtifactStore without browser."""
    observer = PageObserver(artifact_store=mock_artifact_store, run_id="run-99")
    dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

    observation = await observer.capture(
        step_id=5,
        run_id="run-99",
        screenshot_bytes=dummy_png,
    )

    expected_key = "runs/run-99/steps/5_screenshot.png"
    assert observation.screenshot_path == f"stored/{expected_key}"
    mock_artifact_store.save.assert_awaited_once_with(
        key=expected_key,
        data=dummy_png,
        content_type="image/png",
    )


@pytest.mark.anyio
async def test_rrweb_recorder_stop_and_save_with_mock_store(
    mock_artifact_store: MagicMock,
) -> None:
    """Assert RRWebRecorder.stop_and_save saves JSON events payload to ArtifactStore."""
    recorder = RRWebRecorder(artifact_store=mock_artifact_store, run_id="run-101")
    dummy_event = {"type": 4, "data": {"href": "http://gitea.local/"}, "timestamp": 12345}
    recorder._events.append(dummy_event)

    saved_path = await recorder.stop_and_save()

    expected_key = "runs/run-101/rrweb_recording.json"
    assert saved_path == f"stored/{expected_key}"
    assert recorder.recording_path == f"stored/{expected_key}"

    mock_artifact_store.save.assert_awaited_once()
    call_kwargs = mock_artifact_store.save.await_args.kwargs
    assert call_kwargs["key"] == expected_key
    assert call_kwargs["content_type"] == "application/json"
    saved_data = json.loads(call_kwargs["data"].decode("utf-8"))
    assert saved_data == [dummy_event]


@pytest.mark.anyio
async def test_page_observer_stop_recording_persists_rrweb(
    mock_gitea_page: Page,
    mock_artifact_store: MagicMock,
) -> None:
    """Assert PageObserver.stop_recording calls store.save and populates RecordingRef.path."""
    observer = PageObserver(artifact_store=mock_artifact_store, run_id="run-202")
    await observer.start_recording(mock_gitea_page)

    dummy_event = {"type": 2, "data": {"node": {}}, "timestamp": 67890}
    observer.recorder._events.append(dummy_event)

    recording_ref = await observer.stop_recording()

    expected_key = "runs/run-202/rrweb_recording.json"
    assert recording_ref.path == f"stored/{expected_key}"
    mock_artifact_store.save.assert_awaited_once()
    call_kwargs = mock_artifact_store.save.await_args.kwargs
    assert call_kwargs["key"] == expected_key
    assert call_kwargs["content_type"] == "application/json"


@pytest.mark.anyio
async def test_artifact_persistence_with_fake_artifact_store(
    mock_gitea_page: Page,
    sample_step: StepRef,
) -> None:
    """Integration test using the contract FakeArtifactStore port implementation."""
    fake_store = FakeArtifactStore()
    observer = PageObserver(artifact_store=fake_store, run_id="run-fake")

    await mock_gitea_page.goto("http://gitea.local/")
    await observer.start_recording(mock_gitea_page)

    obs = await observer.capture(mock_gitea_page, sample_step)
    assert obs.screenshot_path == "runs/run-fake/steps/1_screenshot.png"
    assert await fake_store.exists("runs/run-fake/steps/1_screenshot.png")

    rec_ref = await observer.stop_recording()
    assert rec_ref.path == "runs/run-fake/rrweb_recording.json"
    assert await fake_store.exists("runs/run-fake/rrweb_recording.json")

    # Read back rrweb JSON from store and verify
    stored_artifact = await fake_store.get("runs/run-fake/rrweb_recording.json")
    assert stored_artifact.ref.content_type == "application/json"
    assert isinstance(json.loads(stored_artifact.data.decode("utf-8")), list)


@pytest.mark.anyio
async def test_artifact_persistence_with_local_fs_store(
    tmp_path: Path,
    mock_gitea_page: Page,
    sample_step: StepRef,
) -> None:
    """Integration test using LocalFsStore against a real directory."""
    fs_store = LocalFsStore(tmp_path)
    observer = PageObserver(artifact_store=fs_store, run_id="run-fs")

    await mock_gitea_page.goto("http://gitea.local/")
    await observer.start_recording(mock_gitea_page)

    obs = await observer.capture(mock_gitea_page, sample_step)
    assert obs.screenshot_path == "runs/run-fs/steps/1_screenshot.png"
    assert (tmp_path / "runs/run-fs/steps/1_screenshot.png").is_file()

    rec_ref = await observer.stop_recording()
    assert rec_ref.path == "runs/run-fs/rrweb_recording.json"
    assert (tmp_path / "runs/run-fs/rrweb_recording.json").is_file()
