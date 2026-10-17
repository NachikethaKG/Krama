"""Data models and schemas for page state observation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.ports.models import ObservedState

__all__ = [
    "NetworkRequest",
    "NetworkSummary",
    "Observation",
    "ObserverStorageError",
    "StepObservation",
    "StepTiming",
]


class NetworkRequest(BaseModel):
    """Details of a network request tracked during observation."""

    model_config = ConfigDict(frozen=True)

    method: str
    url: str
    resource_type: str
    status: int | None = None
    duration_ms: float | None = None
    failed: bool = False
    error_text: str | None = None


class NetworkSummary(BaseModel):
    """Summary of network activity during a step."""

    model_config = ConfigDict(frozen=True)

    request_count: int = 0
    status_codes: dict[int, int] = Field(default_factory=dict)
    failed_requests: list[str] = Field(default_factory=list)
    active_connections: int = 0
    requests_by_type: dict[str, int] = Field(default_factory=dict)


class StepTiming(BaseModel):
    """Execution timing relative to the start of the rrweb recording session (0 ms)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    start_ms: int = Field(ge=0, description="Step start time in milliseconds relative to session start")
    end_ms: int = Field(ge=0, description="Step end time in milliseconds relative to session start")
    duration_ms: int = Field(ge=0, description="Step duration in milliseconds (end_ms - start_ms)")


class ObserverStorageError(RuntimeError):
    """Raised when persisting or retrieving an observer artifact fails."""


class Observation(ObservedState):
    """Complete page observation collected after an action step."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    raw_url: str = ""
    aria_snapshot: str = ""
    screenshot: bytes | str | None = None
    screenshot_path: str | None = None
    rrweb_recording_path: str | None = None
    rrweb_path: str | None = None
    storage_error: str | None = None
    network_summary: NetworkSummary = Field(default_factory=NetworkSummary)
    capture_duration_ms: float = 0.0
    timing: StepTiming | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    duration_ms: int | None = None

    @classmethod
    def create(
        cls,
        *,
        url: str,
        title: str = "",
        raw_url: str = "",
        headings: list[str] | None = None,
        aria_snapshot: str = "",
        aria_excerpt: str = "",
        screenshot: bytes | str | None = None,
        screenshot_path: str | None = None,
        rrweb_recording_path: str | None = None,
        rrweb_path: str | None = None,
        storage_error: str | None = None,
        network_summary: NetworkSummary | None = None,
        capture_duration_ms: float = 0.0,
        captured_at: datetime | None = None,
        timing: StepTiming | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        duration_ms: int | None = None,
    ) -> Observation:
        """Helper constructor ensuring valid defaults and field values."""
        now = captured_at or datetime.now(UTC)
        # Full masked snapshot: the verifier reads `aria_excerpt` through the port and needs every element.
        excerpt = aria_excerpt or aria_snapshot
        resolved_rrweb_path = rrweb_path or rrweb_recording_path

        resolved_timing = timing
        if resolved_timing is None and start_ms is not None and end_ms is not None:
            resolved_duration = duration_ms if duration_ms is not None else max(0, end_ms - start_ms)
            resolved_timing = StepTiming(
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=resolved_duration,
            )

        resolved_start = resolved_timing.start_ms if resolved_timing is not None else start_ms
        resolved_end = resolved_timing.end_ms if resolved_timing is not None else end_ms
        resolved_dur = resolved_timing.duration_ms if resolved_timing is not None else duration_ms

        return cls(
            url=url,
            title=title,
            headings=headings or [],
            aria_excerpt=excerpt,
            screenshot_path=screenshot_path,
            rrweb_recording_path=resolved_rrweb_path,
            rrweb_path=resolved_rrweb_path,
            storage_error=storage_error,
            captured_at=now,
            raw_url=raw_url or url,
            aria_snapshot=aria_snapshot,
            screenshot=screenshot,
            network_summary=network_summary or NetworkSummary(),
            capture_duration_ms=capture_duration_ms,
            timing=resolved_timing,
            start_ms=resolved_start,
            end_ms=resolved_end,
            duration_ms=resolved_dur,
        )

    def to_observed_state_dict(self) -> dict[str, Any]:
        """Return observed_state dict matching step_schema with relative timing."""
        data: dict[str, Any] = {
            "url": self.url,
            "title": self.title,
            "headings": list(self.headings),
            "aria_excerpt": self.aria_excerpt,
            "screenshot_path": self.screenshot_path,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
        }
        if self.timing is not None:
            data["timing"] = {
                "start_ms": self.timing.start_ms,
                "end_ms": self.timing.end_ms,
                "duration_ms": self.timing.duration_ms,
            }
            data["start_ms"] = self.timing.start_ms
            data["end_ms"] = self.timing.end_ms
        return data


StepObservation = Observation
