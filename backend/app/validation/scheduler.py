"""Scheduled validation (#110): re-check stored workflows on a schedule, one at a time, within site limits.

docs/research/phase-4-nachiketha-scheduling-and-rate-limits.md and the decisions in
docs/research/phase-4-decisions-alignment.md (D7, D9):
- every workflow is re-checked every 7 days;
- after `blocked` (the environment stopped it) it backs off: 1 h, 4 h, 24 h, then the 7 days again;
- a failure that looks like drift is replayed once more right away, and counts only if it fails at the same
  step for the same reason; anything else is a flake and changes nothing;
- one replay at a time, through the worker's one browser.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.ports.validation import ReplayOutcome, ValidationBackend, ValidationRecord, WorkflowCandidate
from app.validation.classify import classify, is_drift
from app.validation.limits import SiteLimits

logger = logging.getLogger(__name__)

EVERY = timedelta(days=7)
BACK_OFF = (timedelta(hours=1), timedelta(hours=4), timedelta(hours=24))
"""Wait after 1, 2, 3 `blocked` results in a row; after more, the normal 7 days."""
PER_PASS = 3
"""Workflows validated per pass at most: a pass (one cron tick) shouldn't hold the browser for long."""


def due(c: WorkflowCandidate, now: datetime) -> bool:
    if c.last_validated_at is None:
        return True
    blocked = 0
    for status in c.recent:
        if status != "blocked":
            break
        blocked += 1
    wait = BACK_OFF[blocked - 1] if 0 < blocked <= len(BACK_OFF) else EVERY
    return now - c.last_validated_at >= wait


class ScheduledValidator:
    """`Validator`, called by the worker's arq cron (and `krama validate`)."""

    def __init__(
        self,
        backend: ValidationBackend,
        limits: SiteLimits,
        *,
        per_pass: int = PER_PASS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._backend = backend
        self._limits = limits
        self._per_pass = per_pass
        self._now = now

    async def run_due(self) -> int:
        now = self._now()
        done = 0
        for candidate in await self._backend.candidates():
            if done >= self._per_pass:
                break
            if not due(candidate, now) or not await self._limits.allowed(candidate.site):
                continue
            await self.validate(candidate)
            done += 1
        return done

    async def validate(self, candidate: WorkflowCandidate) -> ValidationRecord:
        """Validate one workflow now, whatever its schedule (the site limits still count it)."""
        await self._limits.started(candidate.site)
        first = await self._backend.replay(candidate.workflow_id)
        outcome, flake = first, None
        if is_drift(first):
            second = await self._backend.replay(candidate.workflow_id)
            if _same_failure(first, second):
                outcome = second
            else:
                outcome, flake = second, first  # the first failure didn't repeat: a flake (D7)
        status = classify(outcome)
        if flake is not None and status == "outdated":
            status = "blocked"  # failed twice, differently: can't tell; don't mark the tutorial outdated
        record = ValidationRecord(
            workflow_id=candidate.workflow_id,
            status=status,
            version_id=outcome.version_id,
            run_id=outcome.run_id,
            drift_details=_details(outcome, flake),
        )
        await self._backend.record(record)
        await self._limits.finished(candidate.site, blocked=status == "blocked")
        logger.info("validated workflow %s: %s (%s)", candidate.workflow_id, status, outcome.reason or "ok")
        return record


def _same_failure(a: ReplayOutcome, b: ReplayOutcome) -> bool:
    return b.result == "failed" and (a.step_seq, a.reason) == (b.step_seq, b.reason)


def _details(outcome: ReplayOutcome, flake: ReplayOutcome | None) -> dict[str, Any]:
    details: dict[str, Any] = {"result": outcome.result}
    if outcome.reason is not None:
        details["reason"] = outcome.reason
    if outcome.step_seq is not None:
        details["step_seq"] = outcome.step_seq
    if outcome.new_version is not None:
        details["new_version"] = outcome.new_version
    # The failed run's evidence (#109 candidates / failed checks, #112 heal reason and scores).
    for key in ("candidates", "failed_checks", "heal", "target", "url"):
        if key in outcome.details:
            details[key] = outcome.details[key]
    if flake is not None:
        details["flake"] = {"reason": flake.reason, "step_seq": flake.step_seq, "run_id": str(flake.run_id)}
    return details
