import pytest
from playwright.async_api import async_playwright

from app.agent.healer import (
    ElementFingerprint,
    LocatorHealer,
    canonicalize_text,
    name_similarity,
    score_candidate,
)
from app.agent.quota import (
    check_and_consume_gemini_heal_quota,
    get_gemini_heal_quota_status,
    reset_gemini_heal_quota,
)
from app.contracts_gen.common_schema import Target


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def get(self, key: str) -> str | None:
        val = self.data.get(key)
        return str(val) if val is not None else None

    async def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self.data:
                del self.data[k]
                count += 1
        return count


def test_canonicalize_and_name_similarity():
    assert canonicalize_text("New repo") == "create repository"
    assert canonicalize_text("Create Repository") == "create repository"
    assert canonicalize_text("Submit PR") == "submit pull request"

    assert name_similarity("New repo", "Create repository") == 1.0
    assert name_similarity("Create repo", "Create repository") >= 0.85
    assert name_similarity("Delete account", "Create repository") < 0.3


def test_scoring_weights():
    stored = ElementFingerprint(
        role="button",
        name="Create Repository",
        form_signature="/repo/create|new",
        attrs={"id": "btn-create", "name": None, "testid": None},
        center=(100.0, 100.0),
    )
    # Identical candidate
    res_identical = score_candidate(stored, stored)
    assert res_identical["score"] == 1.0

    # Renamed candidate ("Make repo" -> name score ~0.5-0.7, but same form, id, position)
    cand_renamed = ElementFingerprint(
        role="button",
        name="Make repo",
        form_signature="/repo/create|new",
        attrs={"id": "btn-create", "name": None, "testid": None},
        center=(105.0, 102.0),
    )
    res_renamed = score_candidate(stored, cand_renamed)
    assert res_renamed["score"] >= 0.75
    assert res_renamed["form_score"] == 1.0
    assert res_renamed["attr_score"] == 1.0


@pytest.mark.anyio
async def test_redis_quota_limit_at_five():
    fake_redis = FakeRedis()
    await reset_gemini_heal_quota(fake_redis)  # type: ignore[arg-type]

    # Calls 1 to 5 should succeed
    for i in range(1, 6):
        allowed = await check_and_consume_gemini_heal_quota(fake_redis)  # type: ignore[arg-type]
        assert allowed is True, f"Call {i} should be permitted"

    # Call 6 must be blocked
    blocked = await check_and_consume_gemini_heal_quota(fake_redis)  # type: ignore[arg-type]
    assert blocked is False

    used, limit = await get_gemini_heal_quota_status(fake_redis)  # type: ignore[arg-type]
    assert used == 6
    assert limit == 5


@pytest.mark.anyio
async def test_healer_deterministic_margin_winner():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # HTML where button was renamed from "New repo" to "Create repository"
        html = """
        <!DOCTYPE html>
        <html>
        <body>
          <form action="/repo/create">
            <input type="text" name="name" value="demo" />
            <button class="primary" id="btn-create">Create repository</button>
          </form>
        </body>
        </html>
        """
        await page.set_content(html)

        healer = LocatorHealer(page, score_threshold=0.85, margin_threshold=0.15)
        target = Target(role="button", name="New repo", selector="#old-broken-btn")
        stored_fp = ElementFingerprint(
            role="button",
            name="New repo",
            form_signature="/repo/create|",
            attrs={"id": "btn-create"},
        )

        res = await healer.heal(target, stored_fp=stored_fp)
        assert res.ok is True
        assert res.heal_type == "deterministic"
        assert res.is_margin_winner is True
        assert res.healed_target is not None
        assert res.healed_target.name == "Create repository"
        assert res.top_score >= 0.85
        assert res.margin >= 0.15

        await browser.close()


@pytest.mark.anyio
async def test_healer_ambiguous_lookalikes_margin_failure():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Colliding buttons with near-identical text and context
        html = """
        <!DOCTYPE html>
        <html>
        <body>
          <button>Cancel</button>
          <button>Cancel & Close</button>
        </body>
        </html>
        """
        await page.set_content(html)

        # Set score_threshold=0.55 so both candidates qualify, but margin < 0.15
        healer = LocatorHealer(page, score_threshold=0.55, margin_threshold=0.15)
        target = Target(role="button", name="Cancel")

        res = await healer.heal(target)
        # Margin is too small between "Cancel" and "Cancel & Close" without vision
        assert res.ok is False
        assert "Ambiguous look-alikes" in res.reason
        assert res.is_margin_winner is False

        await browser.close()


@pytest.mark.anyio
async def test_healer_quota_exhausted_fallback():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        html = """
        <!DOCTYPE html>
        <html><body><h1>Empty Page</h1></body></html>
        """
        await page.set_content(html)

        fake_redis = FakeRedis()
        # Exhaust quota (6 calls)
        for _ in range(6):
            await fake_redis.incr("krama:ratelimit:gemini_heal:2026-10-31")

        # Mock vision locator presence
        class DummyVision:
            pass

        healer = LocatorHealer(
            page,
            redis=fake_redis,  # type: ignore[arg-type]
            vision=DummyVision(),  # type: ignore[arg-type]
        )
        target = Target(role="button", name="Missing button")
        res = await healer.heal(target)

        assert res.ok is False
        assert "Gemini heal daily quota (5/day) exhausted" in res.reason
        assert "retry AI fix" in res.reason

        await browser.close()
