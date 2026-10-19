"""Core PageObserver implementation capturing page state and network activity."""

from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.async_api import Page

from app.observer.masking import blur_bounding_boxes
from app.observer.models import Observation, StepTiming
from app.observer.network import NetworkTracker
from app.observer.recorder import _persist_to_store
from app.observer.rrweb import RRWebRecorder
from app.policy.masking import mask_text
from app.ports import ArtifactStore
from app.ports.models import RecordingRef, StepRef
from app.ports.observer import Observer

# Open dialogs; Gitea's Fomantic UI marks them only with classes (no role=dialog).
_OPEN_DIALOGS = "dialog[open], [role=dialog], [role=alertdialog], .ui.modal.visible"
_DIALOG_LINE = re.compile(r"^\s*- (?:dialog|alertdialog)\b")


def _as_dialog(snapshot: str) -> str:
    """The dialog's ARIA lines under a `- dialog:` line, as Playwright prints a real role=dialog, so readers
    (the policy) can tell what is inside the dialog."""
    lines = snapshot.splitlines()
    if lines and _DIALOG_LINE.match(lines[0]):
        return snapshot
    return "\n".join(["- dialog:", *(f"  {line}" for line in lines)])


class PageObserver(Observer):
    """Observes and captures browser page state after actions.

    Satisfies both `app.ports.observer.Observer` and `app.observer.ObserverPort`.
    Runs screenshot, accessibility snapshot, and title capture concurrently
    using asyncio.gather to keep latency under 1 second.
    """

    def __init__(
        self,
        *,
        artifact_store: ArtifactStore | None = None,
        run_id: str | None = None,
        artifacts_dir: Path | None = None,
        network_tracker: NetworkTracker | None = None,
        recorder: RRWebRecorder | None = None,
    ) -> None:
        self._artifact_store = artifact_store
        self._run_id = run_id
        self._artifacts_dir = artifacts_dir
        self._tracker = network_tracker or NetworkTracker()
        self._recorder = recorder or RRWebRecorder(artifact_store=artifact_store, run_id=run_id)
        if artifact_store is not None and getattr(self._recorder, "artifact_store", None) is None:
            self._recorder._artifact_store = artifact_store
        if run_id is not None and getattr(self._recorder, "run_id", None) is None:
            self._recorder._run_id = run_id
        self._recording: bool = False
        self._recording_started_at: datetime | None = None
        self._attached_page: Page | None = None
        self._step_starts: dict[str, int] = {}
        self._current_step_start_ms: int | None = None
        self._last_step_end_epoch_ms: int | None = None
        self._last_step_timing: StepTiming | None = None

    @property
    def artifact_store(self) -> ArtifactStore | None:
        """Access the injected ArtifactStore port dependency."""
        return self._artifact_store

    @property
    def run_id(self) -> str | None:
        """Access the configured run_id."""
        return self._run_id

    @property
    def recorder(self) -> RRWebRecorder:
        """Access the underlying rrweb session recorder."""
        return self._recorder

    @property
    def network_tracker(self) -> NetworkTracker:
        """Access the underlying network tracker."""
        return self._tracker

    @property
    def recording_start_epoch_ms(self) -> int | None:
        """Baseline epoch timestamp in integer milliseconds when recording started."""
        return self._recorder.recording_start_epoch_ms

    def get_relative_ms(self, epoch_ms: int) -> int:
        """Calculate relative milliseconds from recording start baseline."""
        return self._recorder.get_relative_ms(epoch_ms)

    def _step_key(self, step: StepRef | int | str | None) -> str:
        if step is None:
            return "current"
        if hasattr(step, "seq"):
            return str(step.seq)
        return str(step)

    def start_step(
        self,
        step: StepRef | int | str | None = None,
        *,
        start_epoch_ms: int | None = None,
    ) -> int:
        """Record the start of a step execution in epoch milliseconds."""
        now_ms = int(time.time() * 1000) if start_epoch_ms is None else int(start_epoch_ms)
        key = self._step_key(step)
        self._step_starts[key] = now_ms
        self._current_step_start_ms = now_ms
        return now_ms

    def finish_step(
        self,
        step: StepRef | int | str | None = None,
        *,
        end_epoch_ms: int | None = None,
        start_epoch_ms: int | None = None,
    ) -> StepTiming:
        """Record the completion of a step and compute its relative StepTiming."""
        now_ms = int(time.time() * 1000) if end_epoch_ms is None else int(end_epoch_ms)
        key = self._step_key(step)
        start_ms = start_epoch_ms
        if start_ms is None:
            start_ms = self._step_starts.pop(key, None)
        if start_ms is None:
            start_ms = self._current_step_start_ms
        if start_ms is None:
            start_ms = self._last_step_end_epoch_ms or (self._recorder.recording_start_epoch_ms or now_ms)

        timing = self.calculate_step_timing(int(start_ms), now_ms)
        self._last_step_end_epoch_ms = now_ms
        self._last_step_timing = timing
        return timing

    def calculate_step_timing(
        self,
        step_start_epoch_ms: int,
        step_end_epoch_ms: int,
    ) -> StepTiming:
        """Calculate relative StepTiming from start and end epoch milliseconds."""
        start_rel = self._recorder.get_relative_ms(int(step_start_epoch_ms))
        end_rel = self._recorder.get_relative_ms(int(step_end_epoch_ms))
        if end_rel < start_rel:
            end_rel = start_rel
        return StepTiming(
            start_ms=start_rel,
            end_ms=end_rel,
            duration_ms=end_rel - start_rel,
        )

    def attach(self, page: Page) -> None:
        """Attach the network listener to the page."""
        self._attached_page = page
        self._tracker.attach(page)

    def detach(self) -> None:
        """Detach network listeners."""
        self._tracker.detach()
        self._attached_page = None

    async def start_recording(self, page: Page) -> None:
        """Start tracking and recording session for this run."""
        self.attach(page)
        self._recording = True
        self._recording_started_at = datetime.now(UTC)
        await self._recorder.start(page.context or page)
        self._last_step_end_epoch_ms = self._recorder.recording_start_epoch_ms
        self._step_starts.clear()
        self._current_step_start_ms = None

    async def stop_recording(self) -> RecordingRef:
        """Stop tracking and return recording metadata."""
        if not self._recording or self._recording_started_at is None:
            raise RuntimeError("stop_recording() called before start_recording()")

        events = await self._recorder.stop()
        now = datetime.now(UTC)
        summary = self._tracker.get_summary()
        self._recording = False
        self._step_starts.clear()
        self._current_step_start_ms = None
        record_path = ""
        store = self._artifact_store or self._recorder.artifact_store
        if store is not None:
            effective_run_id = str(self._run_id or self._recorder.run_id or "default")
            key = f"runs/{effective_run_id}/rrweb_recording.json"
            json_bytes = json.dumps(events).encode("utf-8")
            try:
                record_path = await _persist_to_store(
                    store,
                    key=key,
                    data=json_bytes,
                    content_type="application/json",
                )
                self._recorder._recording_path = record_path
            except Exception:
                record_path = ""
        elif self._artifacts_dir:
            out_file = self._artifacts_dir / "recording.json"
            self._recorder.save_to_json(out_file)
            record_path = str(out_file)

        event_count = len(events) if events else summary.request_count

        return RecordingRef(
            path=record_path,  # "" if nothing was stored: never point at a file that doesn't exist
            event_count=event_count,
            started_at=self._recording_started_at,
            ended_at=now,
        )

    async def stop_and_save(
        self,
        run_id: str | None = None,
        *,
        artifact_store: ArtifactStore | None = None,
    ) -> RecordingRef:
        """Stop recording and persist rrweb events to ArtifactStore."""
        if run_id is not None:
            self._run_id = run_id
            self._recorder._run_id = run_id
        if artifact_store is not None:
            self._artifact_store = artifact_store
            self._recorder._artifact_store = artifact_store
        return await self.stop_recording()

    async def capture(
        self,
        page: Page | Any = None,
        step: StepRef | int | str | None = None,
        *,
        step_id: int | str | None = None,
        run_id: str | None = None,
        screenshot_bytes: bytes | None = None,
        artifact_store: ArtifactStore | None = None,
        step_start_epoch_ms: int | None = None,
        step_end_epoch_ms: int | None = None,
        timing: StepTiming | None = None,
    ) -> Observation:
        """Capture the complete page state right after an action.

        Fetches screenshot, ARIA snapshot, headings, and title concurrently via asyncio.gather().
        Persists screenshot via ArtifactStore if configured, recording the path in the observation.
        """
        t0 = time.perf_counter()

        # Handle flexible calling conventions (e.g. capture(step_id, run_id))
        if page is not None and not hasattr(page, "goto") and not hasattr(page, "title"):
            if step_id is None and isinstance(page, (int, str)):
                step_id = page
            if run_id is None and isinstance(step, str):
                run_id = step
            page = None

        effective_run_id = str(run_id or self._run_id or "default")
        if step_id is not None:
            effective_step_id = str(step_id)
        elif step is not None and hasattr(step, "seq"):
            effective_step_id = str(step.seq)
        elif isinstance(step, (int, str)):
            effective_step_id = str(step)
        else:
            effective_step_id = "1"

        store = artifact_store or self._artifact_store

        if page is not None:
            # Ensure network tracker is attached
            if self._attached_page is not page:
                self.attach(page)

            # 1. URL Path extraction (synchronous property)
            raw_url = page.url or ""
            parsed = urllib.parse.urlsplit(raw_url)
            path_url = parsed.path or "/"

            # 2. Concurrently fetch title, ARIA snapshot, screenshot, and headings
            title_task = self._safe_title(page)
            aria_task = self._safe_aria_snapshot(page)
            screenshot_task = (
                self._safe_screenshot(page, step if isinstance(step, StepRef) else None)
                if screenshot_bytes is None
                else asyncio.sleep(0, result=screenshot_bytes)
            )
            headings_task = self._safe_headings(page)

            title, aria_raw, captured_bytes, headings = await asyncio.gather(
                title_task,
                aria_task,
                screenshot_task,
                headings_task,
            )

            aria_masked = _mask_aria_secrets(aria_raw)
            net_summary = self._tracker.snapshot_and_reset()
        else:
            raw_url = ""
            path_url = "/"
            title = ""
            headings = []
            aria_masked = ""
            captured_bytes = screenshot_bytes or b""
            net_summary = self._tracker.snapshot_and_reset()

        # If custom screenshot bytes were injected while page is active, ensure bounding boxes are blurred
        if captured_bytes and page is not None and screenshot_bytes is not None:
            boxes = await self._find_sensitive_bounding_boxes(page)
            if boxes:
                captured_bytes = blur_bounding_boxes(captured_bytes, boxes, radius=15)

        # 4. Save screenshot to artifact store if configured, else fallback to directory
        screenshot_path: str | None = None
        storage_error: str | None = None

        if captured_bytes:
            if store is not None:
                key = f"runs/{effective_run_id}/steps/{effective_step_id}_screenshot.png"
                try:
                    screenshot_path = await _persist_to_store(
                        store,
                        key=key,
                        data=captured_bytes,
                        content_type="image/png",
                    )
                except Exception as err:
                    screenshot_path = None
                    storage_error = str(err)
            elif self._artifacts_dir:
                try:
                    seq_num = int(effective_step_id)
                    filename = f"step_{seq_num:03d}.png"
                except ValueError:
                    filename = f"step_{effective_step_id}.png"
                target_file = self._artifacts_dir / filename
                try:
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    target_file.write_bytes(captured_bytes)
                    screenshot_path = str(target_file)
                except OSError as err:
                    screenshot_path = None
                    storage_error = str(err)

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # 5. Determine relative step timing
        t_capture_end = int(time.time() * 1000)
        end_epoch = step_end_epoch_ms if step_end_epoch_ms is not None else t_capture_end

        if timing is not None:
            step_timing = timing
            self._last_step_end_epoch_ms = end_epoch
        elif step_start_epoch_ms is not None:
            step_timing = self.calculate_step_timing(step_start_epoch_ms, end_epoch)
            self._last_step_end_epoch_ms = end_epoch
        else:
            key = self._step_key(step if step is not None else step_id)
            if key in self._step_starts:
                start_epoch_int = self._step_starts.pop(key)
            elif self._current_step_start_ms is not None:
                start_epoch_int = self._current_step_start_ms
                self._current_step_start_ms = None
            elif self._last_step_end_epoch_ms is not None:
                start_epoch_int = self._last_step_end_epoch_ms
            elif self._recorder.recording_start_epoch_ms is not None:
                start_epoch_int = self._recorder.recording_start_epoch_ms
            else:
                start_epoch_int = end_epoch

            step_timing = self.calculate_step_timing(start_epoch_int, end_epoch)
            self._last_step_end_epoch_ms = end_epoch

        return Observation.create(
            url=mask_text(path_url),
            raw_url=mask_text(raw_url),
            title=mask_text(title),
            headings=[mask_text(h) for h in headings],
            aria_snapshot=aria_masked,
            screenshot=captured_bytes,
            screenshot_path=screenshot_path,
            rrweb_path=getattr(self._recorder, "recording_path", None),
            storage_error=storage_error,
            network_summary=net_summary,
            capture_duration_ms=latency_ms,
            captured_at=datetime.now(UTC),
            timing=step_timing,
        )

    async def _safe_title(self, page: Page) -> str:
        try:
            return await page.title()
        except Exception:
            return ""

    async def _safe_aria_snapshot(self, page: Page) -> str:
        # Prefer landmark role='main' to capture relevant content first, plus any open dialog outside it:
        # Gitea (Fomantic UI) renders dialogs outside <main> and without role=dialog, so a step expecting a
        # field in the dialog could never be verified (#78).
        try:
            snapshot = await page.get_by_role("main").first.aria_snapshot(timeout=600)
            return "\n".join([snapshot, *await self._dialogs_outside_main(page)])
        except Exception:
            pass

        # Fallback to full body snapshot
        try:
            return await page.locator("body").aria_snapshot(timeout=600)
        except Exception:
            return ""

    async def _dialogs_outside_main(self, page: Page) -> list[str]:
        dialogs = page.locator(_OPEN_DIALOGS).filter(visible=True)
        found: list[str] = []
        try:
            for i in range(await dialogs.count()):
                dialog = dialogs.nth(i)
                if await dialog.evaluate("e => !e.closest('main, [role=main]')"):
                    found.append(_as_dialog(await dialog.aria_snapshot(timeout=600)))
        except Exception:
            return found  # a dialog closing mid-read is not an error
        return found

    async def _find_sensitive_bounding_boxes(self, page: Page) -> list[dict[str, float]]:
        """Identify bounding boxes of password inputs and elements marked sensitive."""
        boxes: list[dict[str, float]] = []
        selectors = [
            'input[type="password"]',
            "[data-sensitive]",
            ".krama-mask-text",
            ".krama-block",
            'input[name*="password" i]',
            'input[name*="passwd" i]',
            'input[name*="secret" i]',
            'input[name*="token" i]',
            'input[autocomplete="current-password"]',
            'input[autocomplete="new-password"]',
            # Like the masking before vision calls (app/agent/vision.py): payment fields, one-time codes.
            'input[autocomplete^="cc-"]',
            'input[autocomplete="one-time-code"]',
        ]
        try:
            combined = ", ".join(selectors)
            locators = await page.locator(combined).all()
            for loc in locators:
                try:
                    box = await loc.bounding_box()
                    if box and box.get("width", 0) > 0 and box.get("height", 0) > 0:
                        boxes.append(
                            {
                                "x": float(box["x"]),
                                "y": float(box["y"]),
                                "width": float(box["width"]),
                                "height": float(box["height"]),
                            }
                        )
                except Exception:
                    continue
        except Exception:
            pass
        return boxes

    async def _safe_screenshot(self, page: Page, step: StepRef | None) -> bytes:
        """Capture screenshot and apply Pillow Gaussian blur to sensitive element bounding boxes."""
        try:
            boxes = await self._find_sensitive_bounding_boxes(page)
            raw_bytes = await page.screenshot(
                type="png",
                animations="disabled",
                caret="hide",
                timeout=2000,
            )
            if raw_bytes and boxes:
                return blur_bounding_boxes(raw_bytes, boxes, radius=15)
            return raw_bytes
        except Exception:
            return b""

    async def _safe_headings(self, page: Page) -> list[str]:
        try:
            loc = page.locator("h1, h2, h3")
            texts = await loc.all_inner_texts()
            return [t.strip() for t in texts if t.strip()]
        except Exception:
            return []


_PASSWORD_VALUE_REGEX = re.compile(
    r'((?:textbox|field)\s+"[^"]*(?:password|token|secret)[^"]*":\s*)([^\n]+)',
    re.IGNORECASE,
)


def _mask_aria_secrets(text: str) -> str:
    """Mask password and secret values inside ARIA accessibility tree text."""
    if not text:
        return ""
    masked = mask_text(text)
    return _PASSWORD_VALUE_REGEX.sub(r"\1***", masked)
