"""Self-healing runner: trial execution, post-condition verification, and version persistence (Phase 4).

Decisions (docs/research/phase-4-decisions-alignment.md):
- D8: Deterministic clear-margin heals that pass full re-verification auto-promote
      ("current", "auto-updated"). Gemini heals or ambiguous margins save as "pending_review"
      while the parent workflow remains "outdated".
- D12: At most 5 Gemini heal calls per day; when exhausted -> outdated + "retry AI fix".
Safety: Never heal onto the wrong element! If the trial action or post-condition fails, the candidate
is immediately discarded. If any subsequent step fails, the flow has changed and the heal is discarded.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.executor import ActionExecutor
from app.agent.healer import ElementFingerprint, LocatorHealer
from app.agent.vision import VisionLocator
from app.contracts_gen.common_schema import Action, Target
from app.db.models import WorkflowRow, WorkflowStepRow, WorkflowVersionRow
from app.db.repositories import add_workflow_version

if TYPE_CHECKING:
    from redis.asyncio import Redis


class HealingRunOutcome(BaseModel):
    """Result of running a self-healing workflow repair."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    reason: str
    validation_status: Literal["healed", "heal_pending", "outdated"]
    version_id: UUID | None = None
    version_status: Literal["current", "pending_review", "superseded", "rejected"] | None = None
    revision: int | None = None
    healed_step_seq: int | None = None
    original_target: dict[str, Any] | None = None
    healed_target: dict[str, Any] | None = None
    change_summary: dict[str, Any] | None = None
    trial_verified: bool = False
    all_steps_verified: bool = False


class HealerRunner:
    """Executes locator healing, verifies post-conditions, re-checks flow, and persists new versions."""

    def __init__(
        self,
        page: Page,
        *,
        redis: Redis | None = None,
        vision: VisionLocator | None = None,
        score_threshold: float = 0.85,
        margin_threshold: float = 0.15,
    ) -> None:
        self._page = page
        self._redis = redis
        self._vision = vision
        self._healer = LocatorHealer(
            page,
            redis=redis,
            vision=vision,
            score_threshold=score_threshold,
            margin_threshold=margin_threshold,
        )

    async def execute_and_verify_step(
        self,
        executor: ActionExecutor,
        action_dict: dict[str, Any],
        target_dict: dict[str, Any],
        expected_state_dict: dict[str, Any] | None,
        instruction_text: str | None = None,
    ) -> bool:
        """Executes a step action and verifies simple post-conditions on the live page."""
        action = Action.model_validate(action_dict)
        clean_target = {k: v for k, v in target_dict.items() if k in ("role", "name", "selector") and v}
        target = Target.model_validate(clean_target) if clean_target else None

        res = await executor.execute(action, target, instruction=instruction_text)
        if not res.ok:
            return False

        # Post-condition verification (URL matches, alert/dialog display, etc.)
        if expected_state_dict:
            url_pattern = expected_state_dict.get("url_matches")
            if url_pattern is not None:
                current_path = executor.current_path()
                if not re.search(url_pattern, current_path):
                    return False

            title_contains = expected_state_dict.get("title_contains")
            if title_contains is not None:
                try:
                    title = await self._page.title()
                    if title_contains.lower() not in title.lower():
                        return False
                except PlaywrightError:
                    return False

            visible_el = expected_state_dict.get("visible")
            if visible_el is not None:
                try:
                    role = visible_el.get("role")
                    name = visible_el.get("name")
                    if role and name:
                        loc = self._page.get_by_role(role, name=name).filter(visible=True)
                        if await loc.count() < 1:
                            return False
                except PlaywrightError:
                    return False

        return True

    async def run(
        self,
        workflow: WorkflowRow,
        steps: Sequence[WorkflowStepRow],
        failing_seq: int,
        *,
        session: AsyncSession | None = None,
        stored_fp: ElementFingerprint | None = None,
        run_id: UUID | None = None,
    ) -> HealingRunOutcome:
        """Attempts to self-heal the workflow at failing_seq and verify all remaining steps."""
        sorted_steps = sorted(steps, key=lambda s: s.seq)
        failing_step = next((s for s in sorted_steps if s.seq == failing_seq), None)
        if failing_step is None:
            raise ValueError(f"Step with seq {failing_seq} not found in workflow {workflow.id}")

        clean_orig = {
            k: v for k, v in (failing_step.target or {}).items() if k in ("role", "name", "selector") and v
        }
        orig_target = Target.model_validate(clean_orig)

        # 1. Attempt healing candidate resolution
        healing_res = await self._healer.heal(
            orig_target,
            stored_fp=stored_fp,
            instruction=failing_step.instruction_text,
        )

        if not healing_res.ok or healing_res.healed_target is None:
            return HealingRunOutcome(
                ok=False,
                reason=healing_res.reason,
                validation_status="outdated",
                healed_step_seq=failing_seq,
                original_target=clean_orig,
            )

        healed_target = healing_res.healed_target
        executor = ActionExecutor(self._page)

        # 2. Safety Check: Trial execution of the healed step and assert post-condition
        trial_target_dict = healed_target.model_dump(exclude_none=True)
        trial_ok = await self.execute_and_verify_step(
            executor=executor,
            action_dict=failing_step.action,
            target_dict=trial_target_dict,
            expected_state_dict=failing_step.expected_state,
            instruction_text=failing_step.instruction_text,
        )

        if not trial_ok:
            reason_msg = (
                "Safety check failed: candidate action failed post-condition verification. "
                "Discarding candidate."
            )
            return HealingRunOutcome(
                ok=False,
                reason=reason_msg,
                validation_status="outdated",
                healed_step_seq=failing_seq,
                original_target=clean_orig,
                healed_target=trial_target_dict,
                trial_verified=False,
            )

        # 3. Full workflow re-verification: Execute all subsequent steps
        subsequent_steps = [s for s in sorted_steps if s.seq > failing_seq]
        for sub_step in subsequent_steps:
            sub_ok = await self.execute_and_verify_step(
                executor=executor,
                action_dict=sub_step.action,
                target_dict=sub_step.target,
                expected_state_dict=sub_step.expected_state,
                instruction_text=sub_step.instruction_text,
            )
            if not sub_ok:
                return HealingRunOutcome(
                    ok=False,
                    reason=f"Subsequent step {sub_step.seq} failed after heal: workflow flow has changed.",
                    validation_status="outdated",
                    healed_step_seq=failing_seq,
                    original_target=clean_orig,
                    healed_target=trial_target_dict,
                    trial_verified=True,
                    all_steps_verified=False,
                )

        # 4. Success: Determine version status and validation status (D8)
        if healing_res.is_margin_winner and healing_res.heal_type == "deterministic":
            version_status: Literal["current", "pending_review", "superseded", "rejected"] = "current"
            validation_status: Literal["healed", "heal_pending", "outdated"] = "healed"
        else:
            version_status = "pending_review"
            validation_status = "heal_pending"

        # 5. Build change summary
        field_changes = []
        if orig_target.name != healed_target.name:
            field_changes.append({"field": "target.name", "from": orig_target.name, "to": healed_target.name})
        if orig_target.selector != healed_target.selector:
            field_changes.append(
                {"field": "target.selector", "from": orig_target.selector, "to": healed_target.selector}
            )

        change_summary = {
            "changes": [
                {
                    "seq": failing_seq,
                    "kind": "changed",
                    "category": "behaviour",
                    "field_changes": field_changes,
                    "heal_details": {
                        "heal_type": healing_res.heal_type,
                        "top_score": healing_res.top_score,
                        "margin": healing_res.margin,
                        "is_margin_winner": healing_res.is_margin_winner,
                    },
                }
            ]
        }

        # 6. Build new step rows
        new_step_rows: list[WorkflowStepRow] = []
        for s in sorted_steps:
            t = trial_target_dict if s.seq == failing_seq else s.target
            new_step_rows.append(
                WorkflowStepRow(
                    seq=s.seq,
                    action=s.action,
                    target=t,
                    instruction_text=s.instruction_text,
                    expected_state=s.expected_state,
                    observed_state=s.observed_state,
                    verification=s.verification,
                    risk=s.risk,
                    sensitive=s.sensitive,
                    screenshot_path=s.screenshot_path,
                )
            )

        version_row: WorkflowVersionRow | None = None
        if session is not None:
            version_row = await add_workflow_version(
                session,
                workflow.id,
                source="heal",
                status=version_status,
                steps=new_step_rows,
                change_summary=change_summary,
                parent_version_id=workflow.current_version_id,
                run_id=run_id,
            )

        return HealingRunOutcome(
            ok=True,
            reason=healing_res.reason,
            validation_status=validation_status,
            version_id=version_row.id if version_row else None,
            version_status=version_status,
            revision=version_row.revision if version_row else None,
            healed_step_seq=failing_seq,
            original_target=clean_orig,
            healed_target=trial_target_dict,
            change_summary=change_summary,
            trial_verified=True,
            all_steps_verified=True,
        )
