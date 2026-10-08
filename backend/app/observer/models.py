"""Data models and schemas for page state observation."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.ports.models import ObservedState


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


class Observation(ObservedState):
    """Complete page observation collected after an action step."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    raw_url: str = ""
    aria_snapshot: str = ""
    screenshot: bytes | str | None = None
    network_summary: NetworkSummary = Field(default_factory=NetworkSummary)
    capture_duration_ms: float = 0.0

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
        network_summary: NetworkSummary | None = None,
        capture_duration_ms: float = 0.0,
        captured_at: datetime | None = None,
    ) -> Observation:
        """Helper constructor ensuring valid defaults and field values."""
        now = captured_at or datetime.now(UTC)
        excerpt = aria_excerpt or (aria_snapshot[:500] if aria_snapshot else "")
        return cls(
            url=url,
            title=title,
            headings=headings or [],
            aria_excerpt=excerpt,
            screenshot_path=screenshot_path,
            captured_at=now,
            raw_url=raw_url or url,
            aria_snapshot=aria_snapshot,
            screenshot=screenshot,
            network_summary=network_summary or NetworkSummary(),
            capture_duration_ms=capture_duration_ms,
        )
