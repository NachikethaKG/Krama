"""Automated tests for rrweb timestamp and step timing alignment.

Verifies:
- Happy path: Sequential steps have valid, monotonically increasing relative time ranges
  (0 <= start_ms < end_ms for every step, and step_i.end_ms <= step_{i+1}.start_ms).
- rrweb events falling within step boundaries correctly map to [start_ms, end_ms].
- Edge cases:
  - Step executed before recording starts clamps cleanly to 0 ms without error.
  - Zero-elapsed steps (start_ms == end_ms) handle duration_ms=0 gracefully.
  - Clock drift / backward timestamps clamp end_ms >= start_ms and duration_ms=0.
  - Negative values rejected by StepTiming model validation.
- Integration: Observation and StepObservation expose timing and observed_state dict.
"""

from __future__ import annotations

import asyncio

import pytest
from playwright.async_api import Page
from pydantic import ValidationError

from app.observer import (
    Observation,
    PageObserver,
    RRWebRecorder,
    SessionRecorder,
    StepObservation,
    StepTiming,
)
from app.ports.models import Action, StepRef, Target

pytestmark = pytest.mark.anyio


def _make_step_ref(seq: int, name: str = "Test Button") -> StepRef:
    """Helper to build a contract StepRef."""
    return StepRef(
        seq=seq,
        action=Action(type="click"),
        target=Target(name=name, role="button"),
        instruction_text=f"Click {name}",
    )


async def test_multi_step_happy_path_deterministic() -> None:
    """Verify sequential steps with deterministic time steps have monotonically increasing ranges.

    Asserts:
    - step_1.timing.start_ms == 0 (or near 0)
    - step_1.timing.end_ms <= step_2.timing.start_ms
    - step_2.timing.end_ms <= step_3.timing.start_ms
    - All rrweb events corresponding to step 1 fall within [step_1.timing.start_ms, step_1.timing.end_ms].
    """
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    # 1. Initialize recording baseline at t = 10,000 ms
    base_epoch = 10_000
    recorder.recording_start_epoch_ms = base_epoch
    recorder._is_recording = True
    observer._recording = True
    observer._last_step_end_epoch_ms = base_epoch

    # 2. Step 1: [10_000, 10_250]
    # Event 1a at 10_050, Event 1b at 10_200
    t1_start = 10_000
    t1_end = 10_250
    recorder.add_event({"type": 3, "timestamp": 10_050, "data": {"source": 2}})
    recorder.add_event({"type": 3, "timestamp": 10_200, "data": {"source": 1}})

    obs_1 = await observer.capture(
        step=_make_step_ref(1),
        step_start_epoch_ms=t1_start,
        step_end_epoch_ms=t1_end,
    )

    # 3. Step 2: [10_300, 10_600]
    # Event 2 at 10_450
    t2_start = 10_300
    t2_end = 10_600
    recorder.add_event({"type": 3, "timestamp": 10_450, "data": {"source": 1}})

    obs_2 = await observer.capture(
        step=_make_step_ref(2),
        step_start_epoch_ms=t2_start,
        step_end_epoch_ms=t2_end,
    )

    # 4. Step 3: [10_650, 10_900]
    # Event 3 at 10_800
    t3_start = 10_650
    t3_end = 10_900
    recorder.add_event({"type": 3, "timestamp": 10_800, "data": {"source": 1}})

    obs_3 = await observer.capture(
        step=_make_step_ref(3),
        step_start_epoch_ms=t3_start,
        step_end_epoch_ms=t3_end,
    )

    # Stop recording
    await recorder.stop()

    # Step 1 timing assertions
    assert obs_1.timing is not None
    assert obs_1.timing.start_ms == 0
    assert obs_1.timing.end_ms == 250
    assert obs_1.timing.duration_ms == 250

    # Step 2 timing assertions
    assert obs_2.timing is not None
    assert obs_2.timing.start_ms == 300
    assert obs_2.timing.end_ms == 600
    assert obs_2.timing.duration_ms == 300

    # Step 3 timing assertions
    assert obs_3.timing is not None
    assert obs_3.timing.start_ms == 650
    assert obs_3.timing.end_ms == 900
    assert obs_3.timing.duration_ms == 250

    # Monotonicity checks
    assert obs_1.timing.end_ms <= obs_2.timing.start_ms
    assert obs_2.timing.end_ms <= obs_3.timing.start_ms

    # Relative event containment assertions
    rel_events = recorder.get_relative_events()
    assert len(rel_events) == 4

    step1_events = [ev for ev in rel_events if ev["timestamp"] in (10_050, 10_200)]
    assert len(step1_events) == 2
    for ev in step1_events:
        rel_ts = ev["relative_timestamp"]
        assert obs_1.timing.start_ms <= rel_ts <= obs_1.timing.end_ms, (
            f"Event relative timestamp {rel_ts} must fall within step 1 "
            f"[{obs_1.timing.start_ms}, {obs_1.timing.end_ms}]"
        )


async def test_multi_step_live_page_recording(mock_gitea_page: Page) -> None:
    """Verify live multi-step execution with PageObserver records monotonic timing and aligned events."""
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    # Start session recording on page
    await observer.start_recording(mock_gitea_page)
    assert observer.recording_start_epoch_ms is not None

    # Step 1: Navigate to dashboard
    observer.start_step(1)
    await mock_gitea_page.goto("http://gitea.local/")
    await asyncio.sleep(0.02)
    obs_1 = await observer.capture(mock_gitea_page, step=1)

    # Step 2: Click refresh
    observer.start_step(2)
    await mock_gitea_page.click("#refresh-btn")
    await asyncio.sleep(0.02)
    obs_2 = await observer.capture(mock_gitea_page, step=2)

    # Step 3: Navigate to repo create
    observer.start_step(3)
    await mock_gitea_page.goto("http://gitea.local/repo/create")
    await asyncio.sleep(0.02)
    obs_3 = await observer.capture(mock_gitea_page, step=3)

    ref = await observer.stop_recording()

    # Verify timing presence
    assert obs_1.timing is not None
    assert obs_2.timing is not None
    assert obs_3.timing is not None

    # Criteria 1: start_ms and end_ms are non-negative integers relative to recording start (0 ms)
    assert obs_1.timing.start_ms >= 0
    assert obs_1.timing.start_ms <= 100, "Step 1 starts immediately near session start"
    assert obs_1.timing.start_ms <= obs_1.timing.end_ms

    assert obs_2.timing.start_ms >= 0
    assert obs_2.timing.start_ms <= obs_2.timing.end_ms

    assert obs_3.timing.start_ms >= 0
    assert obs_3.timing.start_ms <= obs_3.timing.end_ms

    # Monotonic sequential progression
    assert obs_1.timing.end_ms <= obs_2.timing.start_ms
    assert obs_2.timing.end_ms <= obs_3.timing.start_ms

    # Verify event counts recorded
    events = recorder.get_events()
    assert len(events) >= 2
    assert ref.event_count >= 2


async def test_automatic_sequential_timing_without_explicit_step_starts() -> None:
    """Verify automatic sequential step chaining when start_step is not explicitly called."""
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    # Start recording
    recorder.recording_start_epoch_ms = 50_000
    recorder._is_recording = True
    observer._recording = True
    observer._last_step_end_epoch_ms = 50_000

    # Step 1 finishes at 50_100
    obs_1 = await observer.capture(step=1, step_end_epoch_ms=50_100)
    # Step 2 finishes at 50_300
    obs_2 = await observer.capture(step=2, step_end_epoch_ms=50_300)
    # Step 3 finishes at 50_550
    obs_3 = await observer.capture(step=3, step_end_epoch_ms=50_550)

    assert obs_1.timing is not None and obs_1.timing.start_ms == 0 and obs_1.timing.end_ms == 100
    assert obs_2.timing is not None and obs_2.timing.start_ms == 100 and obs_2.timing.end_ms == 300
    assert obs_3.timing is not None and obs_3.timing.start_ms == 300 and obs_3.timing.end_ms == 550

    assert obs_1.timing.end_ms <= obs_2.timing.start_ms
    assert obs_2.timing.end_ms <= obs_3.timing.start_ms


async def test_step_executed_before_recording_starts() -> None:
    """Edge case: Step executed before recording starts is clamped cleanly without negative values."""
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    # Recording NOT started (recording_start_epoch_ms is None)
    assert recorder.recording_start_epoch_ms is None
    assert observer.recording_start_epoch_ms is None

    # Capture step before recording
    obs = await observer.capture(
        step=1,
        step_start_epoch_ms=1000,
        step_end_epoch_ms=1500,
    )

    assert obs.timing is not None
    assert obs.timing.start_ms == 0
    assert obs.timing.end_ms == 0
    assert obs.timing.duration_ms == 0
    assert obs.start_ms == 0
    assert obs.end_ms == 0
    assert obs.duration_ms == 0


async def test_step_with_timestamp_before_recording_start_clamped() -> None:
    """Edge case: Step with start_epoch prior to recording baseline is clamped to 0 ms."""
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    # Baseline set at 20_000
    recorder.recording_start_epoch_ms = 20_000

    # Step started at 19_500 (before session start) and ended at 20_200
    timing = observer.calculate_step_timing(step_start_epoch_ms=19_500, step_end_epoch_ms=20_200)

    assert timing.start_ms == 0
    assert timing.end_ms == 200
    assert timing.duration_ms == 200


async def test_immediate_step_completion_zero_duration() -> None:
    """Edge case: Step completed with zero duration handles duration_ms=0 gracefully."""
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    recorder.recording_start_epoch_ms = 10_000

    timing = observer.calculate_step_timing(step_start_epoch_ms=10_500, step_end_epoch_ms=10_500)

    assert timing.start_ms == 500
    assert timing.end_ms == 500
    assert timing.duration_ms == 0


async def test_clock_drift_reverse_timestamps_clamped() -> None:
    """Edge case: Clock drift where end timestamp is earlier than start timestamp is clamped."""
    recorder = RRWebRecorder()
    observer = PageObserver(recorder=recorder)

    recorder.recording_start_epoch_ms = 10_000

    # End is 10_200 while start was 10_400 (clock drifted backwards by 200 ms)
    timing = observer.calculate_step_timing(step_start_epoch_ms=10_400, step_end_epoch_ms=10_200)

    assert timing.start_ms == 400
    assert timing.end_ms == 400, "end_ms must clamp to start_ms when end < start"
    assert timing.duration_ms == 0


def test_step_timing_model_validation() -> None:
    """Verify StepTiming model validates non-negative integers and freezes."""
    timing = StepTiming(start_ms=10, end_ms=50, duration_ms=40)
    assert timing.start_ms == 10
    assert timing.end_ms == 50
    assert timing.duration_ms == 40

    # Negative values must be rejected
    with pytest.raises(ValidationError):
        StepTiming(start_ms=-1, end_ms=10, duration_ms=11)

    with pytest.raises(ValidationError):
        StepTiming(start_ms=0, end_ms=-5, duration_ms=0)

    with pytest.raises(ValidationError):
        StepTiming(start_ms=0, end_ms=10, duration_ms=-1)

    # Immutability (frozen)
    with pytest.raises(ValidationError):
        timing.start_ms = 20  # type: ignore[misc]


def test_observation_and_step_observation_integration() -> None:
    """Verify Observation and StepObservation expose timing fields and to_observed_state_dict."""
    timing = StepTiming(start_ms=120, end_ms=350, duration_ms=230)

    obs = Observation.create(
        url="/repo/create",
        title="Create Repo",
        timing=timing,
    )

    assert obs.timing == timing
    assert obs.start_ms == 120
    assert obs.end_ms == 350
    assert obs.duration_ms == 230

    d = obs.to_observed_state_dict()
    assert d["url"] == "/repo/create"
    assert d["start_ms"] == 120
    assert d["end_ms"] == 350
    assert d["timing"] == {
        "start_ms": 120,
        "end_ms": 350,
        "duration_ms": 230,
    }

    # StepObservation alias check
    assert StepObservation is Observation
    step_obs = StepObservation.create(
        url="/repo/create",
        start_ms=50,
        end_ms=100,
    )
    assert step_obs.timing is not None
    assert step_obs.timing.start_ms == 50
    assert step_obs.timing.end_ms == 100
    assert step_obs.timing.duration_ms == 50


async def test_session_recorder_protocol_conformance_with_timing() -> None:
    """Verify RRWebRecorder conforms to SessionRecorder protocol with timing methods."""
    recorder = RRWebRecorder()
    assert isinstance(recorder, SessionRecorder)

    assert recorder.recording_start_epoch_ms is None
    assert recorder.get_relative_ms(5000) == 0

    recorder.recording_start_epoch_ms = 4000
    assert recorder.recording_start_epoch_ms == 4000
    assert recorder.get_relative_ms(4050) == 50
    assert recorder.get_relative_ms(3000) == 0  # Clamped

    recorder.clear()
    assert recorder.recording_start_epoch_ms is None
    assert recorder.get_relative_ms(4050) == 0
