"""The owner's review queue (#115/#377; D8, D11, D12 in docs/research/phase-4-decisions-alignment.md).

Nothing is stored per item: the queue is derived from the owner's workflows, their versions and validations.

- heal_pending: a version waits for review (an AI-chosen heal, D8). Accept makes it current; reject marks it
  rejected and the workflow stays outdated.
- outdated: the workflow no longer works and nothing waits for review.
- cant_check: its last 3 validations were `blocked` (sign-in, CAPTCHA, site down, ...), D11.
- unstable: 2+ validations in the last 7 days failed once and passed on the confirm replay (D7 flakes), D11.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts_gen.review_schema import ReviewAction, ReviewActionResult, ReviewItem
from app.db import ValidationRow, WorkflowRow, WorkflowVersionRow
from app.db.repositories import refresh_search

CANT_CHECK_AFTER = 3  # blocked validations in a row (D11)
UNSTABLE_FLAKES = 2  # flaky validations ...
UNSTABLE_WINDOW = timedelta(days=7)  # ... within this window (D11)

# Failure reasons (runs' error.details.reason, validation drift_details.reason) in the owner's words.
_REASONS = {
    "locator_miss": "the element it uses is gone or renamed",
    "state_mismatch": "the page didn't end up as expected",
    "action_failed": "an action no longer works",
    "verification_unclear": "nothing proved the step worked",
    "auth_wall": "the site asked to sign in",
    "sign_in_required": "the site asked to sign in",
    "captcha": "the site showed a CAPTCHA",
    "rate_limited": "the site limited requests",
    "site_unreachable": "the site couldn't be reached",
    "reset_failed": "the site couldn't be reset before the check",
    "precondition_failed": "the starting state wasn't there",
    "run_timeout": "the check took too long",
    "high_risk_step": "a step is high risk, so it isn't replayed",
    "secret_not_stored": "a step typed a secret, which is never stored",
}


class ReviewNotFoundError(LookupError):
    """No such item in this owner's queue."""


class ReviewConflictError(RuntimeError):
    """The item can't take this action (e.g. the version no longer waits for review)."""


async def review_items(
    s: AsyncSession, user_id: UUID, *, ai_fix_left: bool, now: datetime
) -> list[ReviewItem]:
    """The owner's queue, newest first. `ai_fix_left`: whether today's Gemini heal budget has calls left."""
    workflows = list((await s.scalars(select(WorkflowRow).where(WorkflowRow.user_id == user_id))).all())
    if not workflows:
        return []
    ids = [w.id for w in workflows]
    pending: dict[UUID, WorkflowVersionRow] = {}
    for v in (
        await s.scalars(
            select(WorkflowVersionRow)
            .where(WorkflowVersionRow.workflow_id.in_(ids), WorkflowVersionRow.status == "pending_review")
            .order_by(WorkflowVersionRow.revision)
        )
    ).all():
        pending[v.workflow_id] = v  # the newest waiting version wins
    validations: dict[UUID, list[ValidationRow]] = defaultdict(list)
    for row in (
        await s.scalars(
            select(ValidationRow)
            .where(ValidationRow.workflow_id.in_(ids))
            .order_by(ValidationRow.ran_at.desc())
        )
    ).all():
        validations[row.workflow_id].append(row)

    items: list[ReviewItem] = []
    for w in workflows:
        item = _item(w, pending.get(w.id), validations[w.id], ai_fix_left=ai_fix_left, now=now)
        if item is not None:
            items.append(item)
    return sorted(items, key=lambda i: i.since, reverse=True)


def _item(
    w: WorkflowRow,
    waiting: WorkflowVersionRow | None,
    checks: list[ValidationRow],
    *,
    ai_fix_left: bool,
    now: datetime,
) -> ReviewItem | None:
    base: dict[str, Any] = {
        "workflow_id": w.id,
        "workflow_title": w.title,
        "target_app": w.target_app,
        "current_revision": w.revision,
    }
    if waiting is not None:
        step = _first_changed_step(waiting.change_summary)
        where = f" for step {step}" if step else ""
        return ReviewItem.model_validate(
            {
                **base,
                "id": f"heal_pending:{waiting.id}",
                "category": "heal_pending",
                "reason": f"An AI-chosen fix{where} waits for your review.",
                "step_seq": step,
                "since": waiting.created_at,
                "pending_revision": waiting.revision,
                "step_diff": waiting.change_summary,
                "actions": ["accept", "reject", "regenerate"],
            }
        )
    if w.status == "outdated":
        last = next((c for c in checks if c.status == "outdated"), None)
        details = (last.drift_details or {}) if last is not None else {}
        actions: list[ReviewAction] = ["regenerate"]
        if ai_fix_left:
            actions.append("retry_ai_fix")
        return ReviewItem.model_validate(
            {
                **base,
                "id": f"outdated:{w.id}",
                "category": "outdated",
                "reason": _sentence(details, fallback="It no longer works on the site."),
                "step_seq": details.get("step_seq"),
                "since": last.ran_at if last is not None else w.updated_at,
                "actions": actions,
            }
        )
    recent = checks[:CANT_CHECK_AFTER]
    if len(recent) == CANT_CHECK_AFTER and all(c.status == "blocked" for c in recent):
        details = recent[0].drift_details or {}
        why = _REASONS.get(str(details.get("reason")), str(details.get("reason") or "unknown"))
        return ReviewItem.model_validate(
            {
                **base,
                "id": f"cant_check:{w.id}",
                "category": "cant_check",
                "reason": f"The last {CANT_CHECK_AFTER} checks were blocked: {why}.",
                "step_seq": details.get("step_seq"),
                "since": recent[-1].ran_at,
                "actions": ["retry_check"],
            }
        )
    flakes = [c for c in checks if now - c.ran_at <= UNSTABLE_WINDOW and (c.drift_details or {}).get("flake")]
    if len(flakes) >= UNSTABLE_FLAKES:
        flake = (flakes[0].drift_details or {})["flake"]
        return ReviewItem.model_validate(
            {
                **base,
                "id": f"unstable:{w.id}",
                "category": "unstable",
                "reason": f"{len(flakes)} checks in the last 7 days failed once and passed on the re-run.",
                "step_seq": flake.get("step_seq") if isinstance(flake, dict) else None,
                "since": flakes[-1].ran_at,
                "actions": ["retry_check"],
            }
        )
    return None


async def accept(s: AsyncSession, user_id: UUID, item_id: str) -> ReviewActionResult:
    """D8: the waiting version becomes current; the workflow's copies follow it and it is verified again."""
    workflow, version = await _waiting(s, user_id, item_id)
    await s.execute(
        update(WorkflowVersionRow)
        .where(WorkflowVersionRow.workflow_id == workflow.id, WorkflowVersionRow.status == "current")
        .values(status="superseded")
    )
    await s.flush()  # one current version at a time (partial unique index)
    version.status = "current"
    workflow.current_version_id = version.id
    workflow.revision = version.revision
    workflow.status = "verified"
    workflow.confidence = version.confidence
    workflow.recording_path = version.recording_path
    workflow.viewport = version.viewport
    await refresh_search(s, workflow)
    await s.flush()
    return ReviewActionResult(
        workflow_id=workflow.id,
        workflow_status="verified",
        revision=workflow.revision,
        message=f"Version {version.revision} is now live.",
    )


async def reject(s: AsyncSession, user_id: UUID, item_id: str) -> ReviewActionResult:
    """D8: the waiting version is rejected; the workflow stays outdated until it's regenerated or fixed."""
    workflow, version = await _waiting(s, user_id, item_id)
    version.status = "rejected"
    workflow.status = "outdated"
    await s.flush()
    return ReviewActionResult(
        workflow_id=workflow.id,
        workflow_status="outdated",
        revision=workflow.revision,
        message=f"Version {version.revision} rejected. Regenerate the tutorial or retry the AI fix.",
    )


async def _waiting(s: AsyncSession, user_id: UUID, item_id: str) -> tuple[WorkflowRow, WorkflowVersionRow]:
    category, _, raw = item_id.partition(":")
    try:
        version_id = UUID(raw)
    except ValueError:
        raise ReviewNotFoundError(item_id) from None
    if category != "heal_pending":
        raise ReviewConflictError("Only a fix waiting for review can be accepted or rejected.")
    version = await s.get(WorkflowVersionRow, version_id, with_for_update=True)
    workflow = await s.get(WorkflowRow, version.workflow_id, with_for_update=True) if version else None
    if version is None or workflow is None or workflow.user_id != user_id:
        raise ReviewNotFoundError(item_id)
    if version.status != "pending_review":
        raise ReviewConflictError(
            f"Version {version.revision} no longer waits for review ({version.status})."
        )
    return workflow, version


def _sentence(details: dict[str, Any], *, fallback: str) -> str:
    reason, step = details.get("reason"), details.get("step_seq")
    if reason is None:
        return fallback
    words = _REASONS.get(str(reason), str(reason))
    return f"Step {step}: {words}." if step else f"{words[0].upper()}{words[1:]}."


def _first_changed_step(diff: dict[str, Any] | None) -> int | None:
    for change in (diff or {}).get("steps", []):
        if change.get("kind") != "same":
            seq = change.get("new_seq") or change.get("old_seq")
            return int(seq) if seq else None
    return None


def utcnow() -> datetime:
    return datetime.now(UTC)
