"""The review queue contract (#377): its fixture parses, has one item per category, and only
heal_pending items can be accepted or rejected."""

import json
from pathlib import Path

from app.contracts_gen.review_schema import ReviewItemList

FIXTURE = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "reviews" / "review-queue.json"


def test_review_fixture_parses_with_one_item_per_category() -> None:
    items = ReviewItemList.model_validate(json.loads(FIXTURE.read_text("utf-8"))).items
    assert {i.category for i in items} == {"outdated", "heal_pending", "unstable", "cant_check"}
    for item in items:
        assert item.id.startswith(f"{item.category}:")
        assert ("accept" in item.actions) == (item.category == "heal_pending")


def test_a_pending_heal_carries_its_step_diff() -> None:
    items = ReviewItemList.model_validate(json.loads(FIXTURE.read_text("utf-8"))).items
    heal = next(i for i in items if i.category == "heal_pending")
    assert heal.step_diff is not None and heal.pending_revision == heal.step_diff.to_revision == 2
