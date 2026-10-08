"""Unit and integration tests for rrweb session recording and navigation continuity."""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import json
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.observer import PageObserver, RRWebRecorder, SessionRecorder, get_rrweb_init_script
from app.observer.rrweb import (
    BENCHMARK_1MIN_DURATION_S,
    BENCHMARK_1MIN_EVENT_COUNT,
    BENCHMARK_1MIN_GZIP_BYTES,
    BENCHMARK_1MIN_JSON_BYTES,
)
from app.ports.models import RecordingRef

pytestmark = pytest.mark.anyio


def _read_json_file(p: Path | str) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _read_gzip_json_file(p: Path | str) -> Any:
    return json.loads(gzip.decompress(Path(p).read_bytes()).decode("utf-8"))


def _file_exists(p: Path | str) -> bool:
    return Path(p).is_file()


def test_rrweb_recorder_protocol_conformance() -> None:
    """Verify that RRWebRecorder satisfies the SessionRecorder protocol."""
    recorder = RRWebRecorder()
    assert isinstance(recorder, SessionRecorder)
    assert not recorder.is_recording
    assert recorder.event_count == 0


def test_get_rrweb_init_script_bundle() -> None:
    """Verify that get_rrweb_init_script bundles the UMD library with the initialization script."""
    script = get_rrweb_init_script()
    assert len(script) > 50000
    # Must contain the critical semicolon delimiter to prevent JavaScript ASI syntax failures
    assert "\n;\n" in script
    assert "__krama_rrweb_emit__" in script
    assert "maskInputOptions" in script


def test_benchmark_constants_defined() -> None:
    """Verify empirical 1-minute benchmark metadata constants are defined."""
    assert BENCHMARK_1MIN_DURATION_S > 40.0
    assert BENCHMARK_1MIN_EVENT_COUNT == 240
    assert BENCHMARK_1MIN_JSON_BYTES > 2_000_000
    assert BENCHMARK_1MIN_GZIP_BYTES < 500_000


async def test_rrweb_event_handling_and_storage_stats(tmp_path: Path) -> None:
    """Verify in-memory event aggregation, timestamp ordering, and JSON/gzip persistence."""
    recorder = RRWebRecorder()
    recorder._is_recording = True

    # Simulate raw events from browser
    raw_ev1: dict[str, Any] = {
        "doc_id": "doc1",
        "url": "http://gitea.local/",
        "seq": 0,
        "event": {"type": 4, "data": {"href": "http://gitea.local/"}, "timestamp": 200},
    }
    raw_ev2: dict[str, Any] = {
        "doc_id": "doc1",
        "url": "http://gitea.local/",
        "seq": 1,
        "event": {"type": 2, "data": {"node": {}}, "timestamp": 100},
    }

    await recorder._handle_browser_event({}, raw_ev1)
    await recorder._handle_browser_event({}, raw_ev2)

    assert recorder.event_count == 2
    events = recorder.get_events()
    # Verified: get_events() returns events sorted by timestamp in ascending order
    assert events[0]["timestamp"] == 100
    assert events[1]["timestamp"] == 200

    # Test storage stats
    stats = recorder.get_storage_stats()
    assert stats["event_count"] == 2
    assert stats["uncompressed_bytes"] > 0
    assert stats["gzip_bytes"] > 0

    # Test JSON persistence
    json_path = recorder.save_to_json(tmp_path / "events.json")
    assert await asyncio.to_thread(_file_exists, json_path)
    loaded = await asyncio.to_thread(_read_json_file, json_path)
    assert len(loaded) == 2

    # Test gzip persistence
    gz_path = recorder.save_to_json(tmp_path / "events.json.gz", compress_gzip=True)
    assert await asyncio.to_thread(_file_exists, gz_path)
    decompressed = await asyncio.to_thread(_read_gzip_json_file, gz_path)
    assert len(decompressed) == 2


async def test_rrweb_recording_across_navigation(mock_gitea_page: Page) -> None:
    """Verify rrweb recording continuity across multi-page navigation."""
    recorder = RRWebRecorder()
    await recorder.start(mock_gitea_page)

    # 1. First page navigation
    await mock_gitea_page.goto("http://gitea.local/")
    await mock_gitea_page.click("#refresh-btn")

    # 2. Second page navigation (survives page lifecycle reset)
    await mock_gitea_page.goto("http://gitea.local/repo/create")
    await mock_gitea_page.fill("#repo_name", "test-repo-continuous")

    events = await recorder.stop()

    assert not recorder.is_recording
    assert len(events) >= 4

    types = [e.get("type") for e in events]
    # Type 4: Meta event, Type 2: FullSnapshot
    assert 4 in types, "Must capture Meta event"
    assert 2 in types, "Must capture FullSnapshot event"

    # Meta events should appear for both navigated pages
    meta_events = [e for e in events if e.get("type") == 4]
    assert len(meta_events) >= 2


async def test_page_observer_recording_lifecycle_with_artifacts(
    mock_gitea_page: Page, tmp_path: Path
) -> None:
    """Verify PageObserver start/stop recording with JSON artifact output."""
    observer = PageObserver(artifacts_dir=tmp_path)

    await observer.start_recording(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/")
    await mock_gitea_page.goto("http://gitea.local/repo/create")

    ref: RecordingRef = await observer.stop_recording()

    assert ref.event_count >= 2
    assert ref.path == str(tmp_path / "recording.json")
    assert ref.started_at <= ref.ended_at

    assert await asyncio.to_thread(_file_exists, ref.path)

    payload = await asyncio.to_thread(_read_json_file, ref.path)
    assert isinstance(payload, list)
    assert len(payload) == ref.event_count


@pytest.mark.gitea
async def test_rrweb_recording_against_live_gitea(gitea_live_url: str, tmp_path: Path) -> None:
    """Integration test against a live Gitea instance if running locally."""
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=True)
        context: BrowserContext = await browser.new_context(base_url=gitea_live_url)
        page: Page = await context.new_page()

        observer = PageObserver(artifacts_dir=tmp_path)
        await observer.start_recording(page)

        await page.goto(f"{gitea_live_url}/")
        await page.goto(f"{gitea_live_url}/user/login")

        ref = await observer.stop_recording()
        assert ref.event_count >= 2
        assert await asyncio.to_thread(_file_exists, ref.path)

        await context.close()
        await browser.close()


async def test_rrweb_recording_on_empty_page(mock_gitea_page: Page) -> None:
    """Verify recorder handles blank and minimal empty pages gracefully without crashing."""
    recorder = RRWebRecorder()
    await recorder.start(mock_gitea_page)
    await mock_gitea_page.goto("about:blank")
    events = await recorder.stop()
    assert isinstance(events, list)
    assert not recorder.is_recording


async def test_rrweb_rapid_navigation(mock_gitea_page: Page) -> None:
    """Verify recording survives rapid successive navigations without unhandled errors."""
    recorder = RRWebRecorder()
    await recorder.start(mock_gitea_page)

    for _ in range(4):
        await mock_gitea_page.goto("http://gitea.local/")
        await mock_gitea_page.goto("http://gitea.local/repo/create")

    events = await recorder.stop()
    assert len(events) >= 4
    assert not recorder.is_recording


async def test_rrweb_script_error_resilience(mock_gitea_page: Page) -> None:
    """Verify client-side page errors and failed network responses do not crash recording."""
    recorder = RRWebRecorder()
    await recorder.start(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/")

    # Inject page-level javascript runtime error
    with contextlib.suppress(Exception):
        await mock_gitea_page.evaluate("() => { throw new Error('Simulated page error'); }")

    # Call error API
    with contextlib.suppress(Exception):
        await mock_gitea_page.evaluate("async () => { await fetch('/api/error'); }")

    events = await recorder.stop()
    assert len(events) >= 1
    assert not recorder.is_recording


async def test_rrweb_closed_context_clean_teardown(mock_gitea_page: Page) -> None:
    """Verify clean teardown when pages or contexts are closed abruptly during recording."""
    recorder = RRWebRecorder()
    await recorder.start(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/")

    # Close page abruptly while recording is active
    await mock_gitea_page.close()

    events = await recorder.stop()
    assert isinstance(events, list)
    assert not recorder.is_recording


def test_rrweb_clear_and_lifecycle_state() -> None:
    """Verify recorder state cleanup via clear() resets in-memory buffers and timestamps."""
    recorder = RRWebRecorder()
    recorder._events.append({"type": 2, "timestamp": 123})
    recorder._raw_records.append({"doc_id": "test", "seq": 1})
    assert recorder.event_count == 1

    recorder.clear()
    assert recorder.event_count == 0
    assert recorder.get_events() == []
    assert recorder.get_raw_records() == []
    assert recorder.started_at is None
    assert recorder.ended_at is None


async def test_page_observer_multiple_start_calls(mock_gitea_page: Page) -> None:
    """Verify multiple calls to start_recording on same page don't throw binding conflicts."""
    observer = PageObserver()
    await observer.start_recording(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/")

    # Second start call without stopping first
    await observer.start_recording(mock_gitea_page)
    await mock_gitea_page.goto("http://gitea.local/repo/create")

    ref = await observer.stop_recording()
    assert ref.event_count >= 1
