"""Ports between scheduled validation (`app.validation`, Nachiketha's module; #110/#111) and the run engine
and database (Vishwas).

Flow (decisions D5-D11 in docs/research/phase-4-decisions-alignment.md; schedule and limits from
docs/research/phase-4-nachiketha-scheduling-and-rate-limits.md):
1. The worker's arq cron calls `Validator.run_due()`.
2. Validation asks `ValidationBackend.candidates()` for the stored workflows and their recent validations,
   and picks the ones that are due (every 7 days, back-off after `blocked`, per-site limits), one at a time.
3. For each, `ValidationBackend.replay(workflow_id)` runs the workflow's stored steps as a reverify run, in
   the calling process with its one browser, self-healing included (#112), and reports the outcome. A failed
   replay is replayed once more before it counts (D7).
4. Validation classifies the outcome (#111) and stores it with `ValidationBackend.record(...)`.
"""

from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import Field

from app.contracts_gen.common_schema import BoundingBox
from app.contracts_gen.workflow_schema import ValidationStatus
from app.ports.models import _Model

__all__ = [
    "ReplayOutcome",
    "StepEvidence",
    "ValidationBackend",
    "ValidationRecord",
    "Validator",
    "WorkflowCandidate",
]


class WorkflowCandidate(_Model):
    """A stored workflow validation may re-check."""

    workflow_id: UUID
    site: str
    """Host (and port) of its target URL, e.g. `github.com` or `127.0.0.1:3001`: limits are per site."""
    target_app: str
    status: str
    """The workflow's status (`verified`, `outdated`, ...)."""
    revision: int
    last_validated_at: datetime | None = None
    recent: tuple[ValidationStatus, ...] = ()
    """Its latest validations' statuses, newest first (at most 5): for back-off and the 3-blocked rule."""


class StepEvidence(_Model):
    """One replayed step next to the same step of the version it validated (#111's visual and position
    checks). Keys are artifact keys (`ArtifactStore.get`); None if there's no screenshot."""

    seq: int
    stored_screenshot: str | None = None
    new_screenshot: str | None = None
    stored_bbox: BoundingBox | None = None
    new_bbox: BoundingBox | None = None


class ReplayOutcome(_Model):
    """How replaying a stored workflow went."""

    result: Literal["verified", "failed", "refused"]
    """refused: it can't be replayed at all (a high-risk step, a typed secret, the reset failed); no run."""
    run_id: UUID | None = None
    version_id: UUID | None = None
    """The version that was replayed (the current one when it started)."""
    reason: str | None = None
    """Why it failed or was refused: the run's `error.details.reason` (`locator_miss`, `state_mismatch`,
    `action_failed`, `policy_stop`, `captcha`, `auth_wall`, `rate_limited`, `destructive_action`,
    `sign_in_required`, `site_unreachable`, `precondition_failed`, `run_timeout`, `crash`, ...) or the refusal
    (`high_risk_step`, `secret_not_stored`, `reset_failed`)."""
    step_seq: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    """The failed run's `error.details`: #109's `candidates` / `failed_checks`, #112's `heal` reason and
    scores."""
    new_version: Literal["current", "pending_review"] | None = None
    """Set when a heal saved a new version (#112): published at once, or waiting for review (D8)."""
    steps: tuple[StepEvidence, ...] = ()
    """The steps that ran, in order."""


class ValidationRecord(_Model):
    """One validation, as stored in the `validations` table."""

    workflow_id: UUID
    status: ValidationStatus
    version_id: UUID | None = None
    run_id: UUID | None = None
    drift_details: dict[str, Any] = Field(default_factory=dict)
    """Why: the failing step and reason, candidates and heal scores, per-step visual/position drift."""


class ValidationBackend(Protocol):
    """Validation's view of stored workflows and the run engine. Implemented by `app.runs` (Vishwas)."""

    async def candidates(self) -> list[WorkflowCandidate]:
        """Every stored workflow on a site validation can replay (local Gitea, GitHub), oldest check first."""
        ...

    async def replay(self, workflow_id: UUID) -> ReplayOutcome:
        """Replay the workflow's current version as a reverify run, here, and wait for it. Never raises for a
        failed or refused replay: that's in the outcome. Raises LookupError for an unknown workflow."""
        ...

    async def record(self, record: ValidationRecord) -> None:
        """Store one validation. `outdated` also marks the workflow outdated; `passed` marks an outdated
        workflow verified again unless a version waits for review. Other statuses leave the workflow as it is
        (`healed` / `heal_pending` were already applied by the heal itself)."""
        ...


class Validator(Protocol):
    """Scheduled validation. Implemented by `app.validation` (#110), called by the worker's arq cron."""

    async def run_due(self) -> int:
        """Validate the workflows that are due, one at a time, within the per-site limits. Returns how many
        it validated."""
        ...
