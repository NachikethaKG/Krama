"""Site notes from earlier verified tutorials (#480, decision K1): what Krama already knows about a site.

Built by code, no LLM: from the user's own verified workflows on the same origin, the pages they went through
and the elements they used there, most used first, at most `MAX_LINES` lines:

    /form: textbox "Item name *" (fill), button "Create item" (click)

Only the same user's workflows (page names in one user's account are not another user's business) and never
the values typed (they can be personal). The text comes from pages, so callers pass it to an LLM as untrusted
data.
"""

from collections import Counter
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import WorkflowRow, WorkflowStepRow

MAX_LINES = 40
MAX_WORKFLOWS = 20
_TITLE = "Pages and elements from earlier verified tutorials on this site:"


def origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


async def site_notes(
    sessions: async_sessionmaker[AsyncSession], user_id: UUID | None, target_url: str
) -> str | None:
    """Notes for planning or deciding on `target_url`, or None when there are no verified workflows there."""
    if user_id is None:
        return None
    origin = origin_of(target_url)
    async with sessions() as s:
        workflows = list(
            await s.scalars(
                select(WorkflowRow)
                .where(
                    WorkflowRow.user_id == user_id,
                    WorkflowRow.status == "verified",
                    WorkflowRow.current_version_id.is_not(None),
                    WorkflowRow.target_url.startswith(origin),
                )
                .order_by(WorkflowRow.updated_at.desc())
                .limit(MAX_WORKFLOWS)
            )
        )
        versions = [w.current_version_id for w in workflows if origin_of(w.target_url) == origin]
        if not versions:
            return None
        steps = list(await s.scalars(select(WorkflowStepRow).where(WorkflowStepRow.version_id.in_(versions))))
    return notes_from_steps(steps)


def notes_from_steps(steps: list[WorkflowStepRow]) -> str | None:
    """The note lines for these stored steps: per page, its elements by how often they were used."""
    used: dict[str, Counter[str]] = {}
    for step in steps:
        target = step.target or {}
        role, name = target.get("role"), target.get("name")
        action = (step.action or {}).get("type", "")
        page = (step.before_state or {}).get("url") or (step.observed_state or {}).get("url") or "/"
        if not role or not name or action in ("navigate", "wait"):
            continue
        used.setdefault(str(page), Counter())[f'{role} "{name}" ({action})'] += 1
    if not used:
        return None
    pages = sorted(used, key=lambda p: -sum(used[p].values()))
    lines = [_TITLE]
    for page in pages:
        elements = ", ".join(e for e, _ in used[page].most_common(8))
        lines.append(f"{page}: {elements}"[:300])
        if len(lines) > MAX_LINES:
            break
    return "\n".join(lines)
