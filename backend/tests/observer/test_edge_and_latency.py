"""Edge cases and performance benchmark tests for PageObserver."""

from __future__ import annotations

import time

import pytest
from playwright.async_api import Page

from app.observer import Observation, PageObserver
from app.ports.models import Action, StepRef, Target

pytestmark = pytest.mark.anyio


async def test_capture_latency_benchmark(mock_gitea_page: Page) -> None:
    """Benchmark observer.capture execution speed; assert < 1.0 s per step."""
    observer = PageObserver()
    observer.attach(mock_gitea_page)

    await mock_gitea_page.goto("http://gitea.local/")

    # 1. Warm-up capture
    warmup_step = StepRef(
        seq=1,
        action=Action(type="navigate", value="/"),
        target=Target(role="main"),
        instruction_text="Warm-up navigation",
    )
    warmup_obs = await observer.capture(mock_gitea_page, step=warmup_step)
    assert warmup_obs.capture_duration_ms < 1000.0

    # 2. Benchmark 5 consecutive captures
    latencies: list[float] = []
    for i in range(2, 7):
        step = StepRef(
            seq=i,
            action=Action(type="click"),
            target=Target(role="button", name="Refresh"),
            instruction_text=f"Benchmark step {i}",
        )

        t0 = time.perf_counter()
        obs = await observer.capture(mock_gitea_page, step=step)
        elapsed_s = time.perf_counter() - t0

        latencies.append(obs.capture_duration_ms)

        # Strict requirement: Capture execution takes less than 1 second (< 1 s)
        assert elapsed_s < 1.0, f"Step {i} took {elapsed_s:.3f} s (exceeded 1.0 s threshold)"
        assert obs.capture_duration_ms < 1000.0
        assert isinstance(obs, Observation)

    avg_latency = sum(latencies) / len(latencies)
    print(f"\n[BENCHMARK] Average capture latency: {avg_latency:.2f} ms across {len(latencies)} steps")
    assert avg_latency < 500.0


async def test_network_summary_captures_http_errors(mock_gitea_page: Page) -> None:
    """Ensure network tracker logs failed endpoints and error HTTP statuses."""
    observer = PageObserver()
    observer.attach(mock_gitea_page)

    await mock_gitea_page.goto("http://gitea.local/")

    # Trigger 500 and 404 endpoints inside page context
    await mock_gitea_page.evaluate(
        """async () => {
            try { await fetch('/api/error'); } catch (e) {}
            try { await fetch('/non-existent-page'); } catch (e) {}
        }"""
    )

    step = StepRef(
        seq=3,
        action=Action(type="wait"),
        target=Target(role="main"),
        instruction_text="Wait after network errors",
    )

    obs = await observer.capture(mock_gitea_page, step=step)

    # Verify status code counting
    assert obs.network_summary.status_codes.get(500, 0) >= 1
    assert obs.network_summary.status_codes.get(404, 0) >= 1

    # Verify failed request tracking
    assert any("500" in err for err in obs.network_summary.failed_requests)


async def test_capture_resilience_on_closed_page(mock_gitea_page: Page) -> None:
    """Verify observer.capture handles a closed page gracefully without uncaught crashes."""
    await mock_gitea_page.goto("http://gitea.local/")
    await mock_gitea_page.close()

    observer = PageObserver()
    step = StepRef(
        seq=99,
        action=Action(type="wait"),
        target=Target(role="main"),
        instruction_text="Capture on closed page",
    )

    obs = await observer.capture(mock_gitea_page, step=step)

    assert isinstance(obs, Observation)
    assert obs.aria_snapshot == ""
    assert obs.screenshot == b""
    assert obs.capture_duration_ms < 1000.0


async def test_recording_lifecycle_and_error_handling(mock_gitea_page: Page) -> None:
    """Verify start_recording and stop_recording lifecycle and state enforcement."""
    observer = PageObserver()

    # Calling stop_recording before start_recording must raise RuntimeError
    with pytest.raises(RuntimeError, match=r"stop_recording.*called before start_recording"):
        await observer.stop_recording()

    await observer.start_recording(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/")

    ref = await observer.stop_recording()

    assert ref.path == "observer/recording.json"
    assert ref.event_count >= 1
    assert ref.started_at <= ref.ended_at

    # Subsequent stop without start must raise RuntimeError again
    with pytest.raises(RuntimeError):
        await observer.stop_recording()
