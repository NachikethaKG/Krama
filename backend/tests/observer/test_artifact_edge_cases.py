"""Edge case and failure handling tests for Observer artifact persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import Page

from app.contracts_gen.common_schema import Action, Target
from app.observer import Observation, ObserverStorageError, PageObserver, RRWebRecorder
from app.ports import ArtifactStore
from app.ports.models import StepRef


@pytest.fixture
def sample_step() -> StepRef:
    return StepRef(
        seq=1,
        action=Action(type="click"),
        target=Target(selector="#refresh-btn"),
        instruction_text="Click refresh",
    )


@pytest.mark.anyio
async def test_capture_storage_io_error_flags_observation_cleanly(
    mock_gitea_page: Page,
    sample_step: StepRef,
) -> None:
    """Simulate an ArtifactStore I/O error; observer flags observation cleanly without crashing."""
    failing_store = MagicMock(spec=ArtifactStore)
    failing_store.save = AsyncMock(side_effect=OSError("Disk write failed"))

    observer = PageObserver(artifact_store=failing_store, run_id="run-err")
    await mock_gitea_page.goto("http://gitea.local/")

    observation = await observer.capture(mock_gitea_page, sample_step)

    # Observer state remains valid and returns Observation with error flagged
    assert observation.screenshot_path is None
    assert observation.storage_error == "Disk write failed"
    assert observation.title == "Dashboard - Gitea"

    # Subsequent capture succeeds and does not leave observer corrupted
    failing_store.save = AsyncMock(return_value="recovered/path.png")
    recovery_obs = await observer.capture(mock_gitea_page, sample_step)
    assert recovery_obs.screenshot_path == "recovered/path.png"
    assert recovery_obs.storage_error is None


@pytest.mark.anyio
async def test_capture_custom_storage_exception_flags_observation() -> None:
    """Verify arbitrary storage exception is caught and recorded without unhandled crash."""
    failing_store = MagicMock(spec=ArtifactStore)
    failing_store.save = AsyncMock(side_effect=RuntimeError("S3 connection timeout"))

    observer = PageObserver(artifact_store=failing_store, run_id="run-custom")
    observation = await observer.capture(
        step_id="step-timeout",
        screenshot_bytes=b"dummy-png",
    )

    assert observation.screenshot_path is None
    assert observation.storage_error == "S3 connection timeout"


@pytest.mark.anyio
async def test_capture_zero_length_screenshot_does_not_call_store() -> None:
    """Handle empty screenshot capture gracefully without touching storage."""
    mock_store = MagicMock(spec=ArtifactStore)
    mock_store.save = AsyncMock()

    observer = PageObserver(artifact_store=mock_store, run_id="run-zero")
    observation = await observer.capture(
        step_id="empty-step",
        screenshot_bytes=b"",
    )

    mock_store.save.assert_not_called()
    assert observation.screenshot_path is None
    assert observation.storage_error is None


@pytest.mark.anyio
async def test_rrweb_recorder_storage_failure_raises_domain_error() -> None:
    """Simulate storage failure during RRWebRecorder.stop_and_save; raises ObserverStorageError."""
    failing_store = MagicMock(spec=ArtifactStore)
    failing_store.save = AsyncMock(side_effect=OSError("Write permission denied"))

    recorder = RRWebRecorder(artifact_store=failing_store, run_id="run-perm-err")
    recorder._events.append({"type": 1, "data": {}})

    with pytest.raises(
        ObserverStorageError,
        match="Failed to persist rrweb recording: Write permission denied",
    ):
        await recorder.stop_and_save()

    # Recorder state is reset and not left in corrupted active recording
    assert recorder.is_recording is False


@pytest.mark.anyio
async def test_rrweb_recorder_empty_events_payload() -> None:
    """Handle zero-length recording events by saving empty JSON array b'[]'."""
    mock_store = MagicMock(spec=ArtifactStore)
    mock_store.save = AsyncMock(return_value="runs/run-empty/rrweb_recording.json")

    recorder = RRWebRecorder(artifact_store=mock_store, run_id="run-empty")
    assert recorder.event_count == 0

    saved_path = await recorder.stop_and_save()

    assert saved_path == "runs/run-empty/rrweb_recording.json"
    mock_store.save.assert_awaited_once_with(
        key="runs/run-empty/rrweb_recording.json",
        data=b"[]",
        content_type="application/json",
    )


@pytest.mark.anyio
async def test_page_observer_stop_recording_storage_failure_handles_cleanly(
    mock_gitea_page: Page,
) -> None:
    """PageObserver.stop_recording handles storage failure cleanly without crashing."""
    failing_store = MagicMock(spec=ArtifactStore)
    failing_store.save = AsyncMock(side_effect=OSError("Storage full"))

    observer = PageObserver(artifact_store=failing_store, run_id="run-full")
    await observer.start_recording(mock_gitea_page)

    rec_ref = await observer.stop_recording()

    # State reset and fallback path returned without unhandled crash
    assert observer._recording is False
    assert rec_ref.path == "observer/recording.json"


def test_observation_model_schema_compatibility() -> None:
    """Verify Observation model schema holds screenshot_path, rrweb_path, and raw screenshot bytes."""
    raw_bytes = b"\x89PNG\r\n\x1a\n"
    obs = Observation.create(
        url="/repo/test",
        title="Test Repo",
        screenshot=raw_bytes,
        screenshot_path="runs/1/steps/1_screenshot.png",
        rrweb_path="runs/1/rrweb_recording.json",
    )

    assert obs.screenshot == raw_bytes
    assert obs.screenshot_path == "runs/1/steps/1_screenshot.png"
    assert obs.rrweb_path == "runs/1/rrweb_recording.json"
    assert obs.rrweb_recording_path == "runs/1/rrweb_recording.json"
    assert obs.storage_error is None
