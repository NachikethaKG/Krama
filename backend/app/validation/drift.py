"""Drift signals and the drift class (#111): how much each replayed step's page looks and sits different from
the stored step, and whether the change is one to ignore, one that was healed, or a changed flow.

docs/research/phase-4-nachiketha-drift-detection-signals.md and phase-4-nachiketha-classifying-drift.md,
within the decided rules (D8-D10 in docs/research/phase-4-decisions-alignment.md):
- the target's box centre moving more than 30 px, or a visibly different screenshot, is cosmetic drift when
  every step still verified: the status stays `passed` (D10), the signals only explain it;
- a heal (published or waiting for review) is the "moved / renamed" class;
- a repeated locator miss, state mismatch or failed action is a changed flow: `outdated`.
The visual diff is CPU-only and cheap: both screenshots shrunk to grayscale thumbnails, compared by pixel.
ARIA evidence comes from the replay itself: the candidates and heal scores (#109, #112) and the failed checks.
"""

import io
from typing import Any, Literal

from PIL import Image, ImageChops

from app.contracts_gen.workflow_schema import ValidationStatus
from app.ports.artifacts import ArtifactStore
from app.ports.models import ArtifactNotFoundError, InvalidArtifactKeyError
from app.ports.validation import StepEvidence

SHIFT_PX = 30.0
"""A box centre moving at most this far is layout noise (an alert banner, padding)."""
THUMB = (160, 100)
PIXEL_DELTA = 32
"""A thumbnail pixel counts as changed when its gray level moved by more than this (of 255)."""
VISUAL_CHANGE = 0.05
"""A step looks different when more than this share of its thumbnail pixels changed."""

type DriftClass = Literal["ignore", "heal", "outdated"]


async def step_signals(
    steps: tuple[StepEvidence, ...], artifacts: ArtifactStore | None
) -> list[dict[str, Any]]:
    """Per replayed step: how far the target's box moved (px) and what share of the screenshot changed."""
    out = []
    for step in steps:
        signal: dict[str, Any] = {"seq": step.seq}
        if step.stored_bbox is not None and step.new_bbox is not None:
            signal["shift_px"] = round(_centre_shift(step.stored_bbox, step.new_bbox), 1)
        if artifacts is not None and step.stored_screenshot and step.new_screenshot:
            change = await _visual_change(artifacts, step.stored_screenshot, step.new_screenshot)
            if change is not None:
                signal["visual_change"] = round(change, 3)
        out.append(signal)
    return out


def drift_class(
    status: ValidationStatus, signals: list[dict[str, Any]]
) -> tuple[DriftClass | None, str | None]:
    """The drift class and a short reason, or (None, None) when nothing can be said (blocked, skipped)."""
    if status in ("healed", "heal_pending"):
        return "heal", "an element was renamed or moved, and self-healing found it again"
    if status == "outdated":
        return "outdated", "a step no longer works the same way (a changed flow)"
    if status != "passed":
        return None, None
    moved = [s["seq"] for s in signals if s.get("shift_px", 0) > SHIFT_PX]
    looks = [s["seq"] for s in signals if s.get("visual_change", 0) > VISUAL_CHANGE]
    if moved or looks:
        parts = ([f"step {', '.join(map(str, moved))} moved more than {SHIFT_PX:g} px"] if moved else []) + (
            [f"step {', '.join(map(str, looks))} looks different"] if looks else []
        )
        return "ignore", "cosmetic: " + "; ".join(parts) + ", every step still verified"
    return "ignore", "no change"


def _centre_shift(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    ax, ay = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx, by = b[0] + b[2] / 2, b[1] + b[3] / 2
    return float(((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5)


async def _visual_change(artifacts: ArtifactStore, stored_key: str, new_key: str) -> float | None:
    """Share (0..1) of thumbnail pixels whose gray level moved by more than PIXEL_DELTA. None if a screenshot
    can't be read."""
    try:
        stored = (await artifacts.get(stored_key)).data
        new = (await artifacts.get(new_key)).data
    except (ArtifactNotFoundError, InvalidArtifactKeyError):
        return None
    try:
        a, b = (_thumbnail(data) for data in (stored, new))
    except OSError:
        return None
    diff = ImageChops.difference(a, b)
    changed = sum(count for level, count in enumerate(diff.histogram()) if level > PIXEL_DELTA)
    return changed / (THUMB[0] * THUMB[1])


def _thumbnail(data: bytes) -> Image.Image:
    with Image.open(io.BytesIO(data)) as image:
        return image.convert("L").resize(THUMB, Image.Resampling.BILINEAR)
