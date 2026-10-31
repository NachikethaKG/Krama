"""Self-healing locator cascade, candidate similarity scoring, and margin evaluation (Phase 4).

Decisions (docs/research/phase-4-decisions-alignment.md):
- D8: Only deterministic, margin-winning heals auto-promote; Gemini heals are pending_review.
- D12: At most 5 Gemini heal calls per day in Redis; when exhausted -> outdated + "retry AI fix".
Never heals onto the wrong element: scores role + name + container context + form signature
+ stable attributes + spatial position, and enforces a margin over the second-best candidate.
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Literal

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page
from pydantic import BaseModel, ConfigDict, Field

from app.agent.context import ElementContext, element_context
from app.agent.quota import check_and_consume_gemini_heal_quota
from app.agent.vision import VisionLocator
from app.contracts_gen.common_schema import Target
from app.verifier.aria import parse_aria_snapshot

if TYPE_CHECKING:
    from redis.asyncio import Redis

# Common web/dev domain synonym canonical mapping
SYNONYMS: dict[str, str] = {
    "repo": "repository",
    "repos": "repositories",
    "pr": "pull request",
    "prs": "pull requests",
    "btn": "button",
    "dir": "directory",
    "dirs": "directories",
    "doc": "documentation",
    "docs": "documentation",
    "auth": "authentication",
    "org": "organization",
    "sub": "subscription",
    "cfg": "configuration",
    "config": "configuration",
    "settings": "preferences",
    "prefs": "preferences",
    "new": "create",
    "add": "create",
    "remove": "delete",
    "del": "delete",
    "trash": "delete",
    "sign in": "log in",
    "signin": "log in",
    "login": "log in",
    "sign out": "log out",
    "signout": "log out",
    "logout": "log out",
}

FORM_JS = """e => {
  const f = e.form || e.closest('form');
  if (!f) return null;
  const a = f.querySelector('input[name=action]');
  return (f.getAttribute('action') || '') + '|' + (a ? a.value : '');
}"""

ATTRS_JS = """e => ({
  id: e.id || null,
  name: e.getAttribute('name') || null,
  testid: e.getAttribute('data-testid') || e.getAttribute('data-test') || null
})"""

CENTER_JS = """e => {
  const b = e.getBoundingClientRect();
  return [b.x + window.scrollX + b.width / 2, b.y + window.scrollY + b.height / 2];
}"""


def canonicalize_text(text: str) -> str:
    """Normalizes text by replacing synonyms, removing punctuation, and stripping whitespace."""
    norm = text.lower().strip(" *\"'")
    for phrase, rep in sorted(SYNONYMS.items(), key=lambda x: len(x[0]), reverse=True):
        if " " in phrase:
            norm = re.sub(rf"\b{re.escape(phrase)}\b", rep, norm)
    tokens = re.findall(r"\b\w+\b", norm)
    canonical = [SYNONYMS.get(t, t) for t in tokens]
    return " ".join(canonical)


def name_similarity(stored: str | None, candidate: str | None) -> float:
    """Computes hybrid string similarity with domain synonym mapping."""
    if not stored or not candidate:
        return 1.0 if stored == candidate else 0.0

    c_stored = canonicalize_text(stored)
    c_cand = canonicalize_text(candidate)

    if c_stored == c_cand:
        return 1.0

    tok_s = set(c_stored.split())
    tok_c = set(c_cand.split())
    jaccard = len(tok_s & tok_c) / max(len(tok_s | tok_c), 1)
    seq_ratio = SequenceMatcher(None, c_stored, c_cand).ratio()
    return round(0.4 * jaccard + 0.6 * seq_ratio, 3)


class ElementFingerprint(BaseModel):
    """Structural, semantic and spatial fingerprint of a target element."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    name: str
    context: ElementContext | None = None
    form_signature: str | None = None
    attrs: dict[str, str | None] = Field(default_factory=dict)
    center: tuple[float, float] | None = None


class ScoredCandidate(BaseModel):
    """A candidate element scored against the stored target fingerprint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    name: str
    selector: str
    score: float
    name_score: float
    context_score: float
    form_score: float
    attr_score: float
    position_score: float
    is_margin_winner: bool = False
    margin_to_second: float = 0.0


class HealingResult(BaseModel):
    """Outcome of locator self-healing attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: bool
    healed_target: Target | None = None
    candidates: list[ScoredCandidate] = Field(default_factory=list)
    heal_type: Literal["deterministic", "gemini"] | None = None
    is_margin_winner: bool = False
    top_score: float = 0.0
    margin: float = 0.0
    reason: str


async def capture_fingerprint(locator: Locator) -> ElementFingerprint | None:
    """Reads the element's fingerprint from the live DOM before acting."""
    try:
        if await locator.count() != 1:
            return None
        handle = await locator.element_handle()
        if handle is None:
            return None

        snap = parse_aria_snapshot(await locator.aria_snapshot())
        ctx = await element_context(locator)
        form = await handle.evaluate(FORM_JS)
        attrs = await handle.evaluate(ATTRS_JS)
        center_raw = await handle.evaluate(CENTER_JS)
        center = (float(center_raw[0]), float(center_raw[1])) if center_raw else None

        role = snap[0].role if snap else "button"
        name = snap[0].label() if snap else ""

        return ElementFingerprint(
            role=role,
            name=name,
            context=ctx,
            form_signature=form,
            attrs=attrs,
            center=center,
        )
    except PlaywrightError:
        return None


def score_candidate(stored: ElementFingerprint, cand: ElementFingerprint) -> dict[str, float]:
    """Computes component and composite similarity scores (0.0 to 1.0)."""
    s_name = name_similarity(stored.name, cand.name)

    # Context score: 1.0 exact match, 0.5 same container, 0.0 mismatch
    sc, cc = stored.context, cand.context
    if sc == cc:
        s_context = 1.0
    elif sc and cc and sc.container == cc.container:
        s_context = 0.5
    else:
        s_context = 0.0

    # Form score: 1.0 if inside same form signature
    s_form = 1.0 if (stored.form_signature and stored.form_signature == cand.form_signature) else 0.0

    # Attribute score: 1.0 if testid or id/name matches
    sa, ca = stored.attrs, cand.attrs
    if sa.get("testid") and sa.get("testid") == ca.get("testid"):
        s_attr = 1.0
    else:
        stable_keys = [k for k in ("id", "name") if sa.get(k)]
        s_attr = (1.0 if any(sa[k] == ca.get(k) for k in stable_keys) else 0.0) if stable_keys else 0.5

    # Spatial position score: decays over 500px distance
    if stored.center and cand.center:
        dist = math.sqrt((stored.center[0] - cand.center[0]) ** 2 + (stored.center[1] - cand.center[1]) ** 2)
        s_pos = max(0.0, 1.0 - dist / 500.0)
    else:
        s_pos = 0.0

    # Composite weighting from research
    total = 0.30 * s_name + 0.20 * s_context + 0.20 * s_form + 0.20 * s_attr + 0.10 * s_pos
    return {
        "score": round(total, 3),
        "name_score": round(s_name, 3),
        "context_score": round(s_context, 3),
        "form_score": round(s_form, 3),
        "attr_score": round(s_attr, 3),
        "position_score": round(s_pos, 3),
    }


class LocatorHealer:
    """Finds, scores, and re-grounds candidates when a locator breaks."""

    def __init__(
        self,
        page: Page,
        redis: Redis | None = None,
        vision: VisionLocator | None = None,
        *,
        score_threshold: float = 0.85,
        margin_threshold: float = 0.15,
    ) -> None:
        self._page = page
        self._redis = redis
        self._vision = vision
        self._score_threshold = score_threshold
        self._margin_threshold = margin_threshold

    async def heal(
        self,
        target: Target,
        stored_fp: ElementFingerprint | None = None,
        *,
        instruction: str | None = None,
    ) -> HealingResult:
        """Executes the fallback healing cascade for an unresolved target."""
        role = target.role or "button"
        name = target.name or ""

        # Build baseline fingerprint if none was stored
        if stored_fp is None:
            stored_fp = ElementFingerprint(role=role, name=name)

        # 1. Semantic test attributes direct match check
        test_attrs = [f"[data-testid='{name}']", f"[data-test='{name}']"]
        for sel in test_attrs:
            try:
                loc = self._page.locator(sel).filter(visible=True)
                if await loc.count() == 1:
                    healed = Target(role=role, name=name, selector=sel)
                    return HealingResult(
                        ok=True,
                        healed_target=healed,
                        heal_type="deterministic",
                        is_margin_winner=True,
                        top_score=1.0,
                        margin=1.0,
                        reason=f"Found exact semantic test attribute match '{sel}'.",
                    )
            except PlaywrightError:
                pass

        # 2. Extract and score visible candidates with the same ARIA role
        scored: list[ScoredCandidate] = []
        try:
            loc = self._page.get_by_role(role).filter(visible=True)  # type: ignore[arg-type]
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                fp = await capture_fingerprint(el)
                if fp is None:
                    continue

                scores = score_candidate(stored_fp, fp)
                # Formulate resilient selector
                cand_name = fp.name
                sel = f"role={role}[name='{cand_name}']"
                scored.append(
                    ScoredCandidate(
                        role=role,
                        name=cand_name,
                        selector=sel,
                        score=scores["score"],
                        name_score=scores["name_score"],
                        context_score=scores["context_score"],
                        form_score=scores["form_score"],
                        attr_score=scores["attr_score"],
                        position_score=scores["position_score"],
                    )
                )
        except PlaywrightError:
            pass

        scored.sort(key=lambda c: -c.score)

        # 3. Deterministic clear-margin evaluation
        if scored:
            top = scored[0]
            second_score = scored[1].score if len(scored) > 1 else 0.0
            margin = round(top.score - second_score, 3)

            # Update margin metadata on top candidate
            top = top.model_copy(
                update={"margin_to_second": margin, "is_margin_winner": margin >= self._margin_threshold}
            )
            scored[0] = top

            if top.score >= self._score_threshold and margin >= self._margin_threshold:
                # Decisive winner
                healed = Target(role=top.role, name=top.name, selector=top.selector)
                msg = (
                    f"Deterministic winner: '{top.name}' scored {top.score:.2f} "
                    f"(margin: {margin:.2f} >= {self._margin_threshold})."
                )
                return HealingResult(
                    ok=True,
                    healed_target=healed,
                    candidates=scored[:5],
                    heal_type="deterministic",
                    is_margin_winner=True,
                    top_score=top.score,
                    margin=margin,
                    reason=msg,
                )

        # 4. Ambiguous candidates or below threshold: Gemini Vision Fallback (gated by D12 quota)
        if self._vision is not None and self._redis is not None:
            has_quota = await check_and_consume_gemini_heal_quota(self._redis)
            if not has_quota:
                msg = "Gemini heal daily quota (5/day) exhausted. Workflow marked outdated ('retry AI fix')."
                return HealingResult(
                    ok=False,
                    candidates=scored[:5],
                    top_score=scored[0].score if scored else 0.0,
                    margin=scored[0].margin_to_second if scored else 0.0,
                    reason=msg,
                )

            # Attempt Gemini Vision re-grounding
            try:
                result = await self._vision.point(self._page, target, instruction)
                if result.point is not None:
                    x, y = result.point
                    role_locs = self._page.get_by_role(role).filter(visible=True)  # type: ignore[arg-type]
                    count = await role_locs.count()
                    hits = []
                    for i in range(count):
                        cand_el = role_locs.nth(i)
                        b = await cand_el.bounding_box()
                        if (
                            b
                            and (b["x"] <= x <= b["x"] + b["width"])
                            and (b["y"] <= y <= b["y"] + b["height"])
                        ):
                            hits.append(cand_el)
                    if len(hits) == 1:
                        picked = hits[0]
                        fp = await capture_fingerprint(picked)
                        name_found = fp.name if fp else target.name
                        sel = f"role={role}[name='{name_found}']"
                        healed = Target(role=role, name=name_found, selector=sel)
                        msg = f"Gemini AI re-grounded element to '{name_found}'. Pending human review (D8)."
                        return HealingResult(
                            ok=True,
                            healed_target=healed,
                            candidates=scored[:5],
                            heal_type="gemini",
                            is_margin_winner=False,  # Gemini heals always require human review (D8)
                            top_score=1.0,
                            margin=0.0,
                            reason=msg,
                        )
            except Exception:
                pass  # Fall through to unhealable

        # 5. Healing Failed: Ambiguous or no viable candidate
        if scored and scored[0].score >= self._score_threshold:
            # Margin failure (colliding look-alikes)
            top = scored[0]
            msg = (
                f"Ambiguous look-alikes: top candidate '{top.name}' margin "
                f"({top.margin_to_second:.2f}) < {self._margin_threshold}."
            )
            return HealingResult(
                ok=False,
                candidates=scored[:5],
                top_score=top.score,
                margin=top.margin_to_second,
                reason=msg,
            )

        return HealingResult(
            ok=False,
            candidates=scored[:5],
            top_score=scored[0].score if scored else 0.0,
            margin=0.0,
            reason=f"No viable candidate found for {target.role} '{target.name}'.",
        )
