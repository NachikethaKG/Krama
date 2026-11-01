"""Drift signals and classes (#111): box shift, a CPU visual diff of screenshots, ignore / heal / outdated."""

import io
from uuid import uuid4

import pytest
from PIL import Image, ImageDraw

from app.ports.fakes import FakeArtifactStore, FakeValidationBackend
from app.ports.validation import ReplayOutcome, StepEvidence, WorkflowCandidate
from app.validation import ScheduledValidator
from app.validation.drift import drift_class, step_signals

pytestmark = pytest.mark.anyio


def png(block_at: tuple[int, int] | None = None) -> bytes:
    """A 1280x800 'page': white, with a dark 300x200 block (a dialog, a banner) where asked."""
    image = Image.new("RGB", (1280, 800), "white")
    if block_at is not None:
        x, y = block_at
        ImageDraw.Draw(image).rectangle((x, y, x + 300, y + 200), fill="#202020")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


async def store_with(**shots: bytes) -> FakeArtifactStore:
    store = FakeArtifactStore()
    for key, data in shots.items():
        await store.put(f"runs/{key}.png", data, "image/png")
    return store


async def test_the_same_page_has_no_drift_and_a_new_dialog_looks_different() -> None:
    store = await store_with(old=png(), same=png(), dialog=png((490, 300)))
    steps = (
        StepEvidence(seq=1, stored_screenshot="runs/old.png", new_screenshot="runs/same.png",
                     stored_bbox=(100, 100, 80, 30), new_bbox=(100, 110, 80, 30)),
        StepEvidence(seq=2, stored_screenshot="runs/old.png", new_screenshot="runs/dialog.png",
                     stored_bbox=(100, 100, 80, 30), new_bbox=(100, 300, 80, 30)),
    )  # fmt: skip

    signals = await step_signals(steps, store)

    assert signals[0] == {"seq": 1, "shift_px": 10.0, "visual_change": 0.0}
    assert signals[1]["shift_px"] == 200.0 and 0.04 < signals[1]["visual_change"] < 0.1  # 300x200 of 1280x800


async def test_missing_screenshots_or_boxes_give_only_what_can_be_measured() -> None:
    signals = await step_signals(
        (StepEvidence(seq=1, stored_screenshot="runs/gone.png", new_screenshot="runs/also-gone.png"),),
        FakeArtifactStore(),
    )

    assert signals == [{"seq": 1}]


@pytest.mark.parametrize(
    ("status", "signals", "klass", "says"),
    [
        ("passed", [{"seq": 1, "shift_px": 4.0, "visual_change": 0.0}], "ignore", "no change"),
        ("passed", [{"seq": 2, "shift_px": 45.0}], "ignore", "step 2 moved more than 30 px"),
        ("passed", [{"seq": 3, "visual_change": 0.2}], "ignore", "step 3 looks different"),
        ("healed", [], "heal", "self-healing found it again"),
        ("heal_pending", [], "heal", "renamed or moved"),
        ("outdated", [], "outdated", "changed flow"),
        ("blocked", [{"seq": 1, "shift_px": 90.0}], None, None),
        ("skipped", [], None, None),
    ],
)
def test_the_drift_class(
    status: str, signals: list[dict[str, object]], klass: str | None, says: str | None
) -> None:
    got, why = drift_class(status, signals)  # type: ignore[arg-type]

    assert got == klass
    assert (why is None) if says is None else (why is not None and says in why)


async def test_a_validation_records_its_signals_and_class() -> None:
    store = await store_with(old=png(), new=png((490, 300)))
    c = WorkflowCandidate.model_validate(
        {
            "workflow_id": uuid4(),
            "site": "127.0.0.1:3001",
            "target_app": "gitea",
            "status": "verified",
            "revision": 1,
        }
    )
    evidence = StepEvidence(seq=1, stored_screenshot="runs/old.png", new_screenshot="runs/new.png")
    backend = FakeValidationBackend(
        [c], {c.workflow_id: [ReplayOutcome(result="verified", steps=(evidence,))]}
    )

    class Open:
        async def allowed(self, site: str) -> bool:
            return True

        async def started(self, site: str) -> None:
            pass

        async def finished(self, site: str, *, blocked: bool) -> None:
            pass

    record = await ScheduledValidator(backend, Open(), artifacts=store).validate(c)

    assert record.status == "passed"  # D10: cosmetic drift never changes the status
    assert (
        record.drift_details["drift_class"] == "ignore"
        and "looks different" in record.drift_details["drift_reason"]
    )
    assert record.drift_details["signals"][0]["visual_change"] > 0.05
