"""What a replay's outcome means for the tutorial: the decided table (D5-D11 in
docs/research/phase-4-decisions-alignment.md, docs/research/phase-4-together-drift-rules.md).

Only evidence about the workflow makes it `outdated`. The environment (a CAPTCHA, a login wall, a rate limit,
a failed reset, the site down) never does: that's `blocked`, and the workflow keeps its status.
"""

from app.contracts_gen.workflow_schema import ValidationStatus
from app.ports.validation import ReplayOutcome

DRIFT_REASONS = frozenset(
    {"locator_miss", "state_mismatch", "action_failed", "destructive_action", "task_incomplete"}
)
"""Failures that say the page or the flow changed. A destructive target (after a heal, or one the policy now
calls destructive) needs a human, so it counts as drift too."""
NOT_REPLAYABLE = frozenset({"high_risk_step", "secret_not_stored"})


def classify(outcome: ReplayOutcome) -> ValidationStatus:
    if outcome.result == "refused":
        return "skipped" if outcome.reason in NOT_REPLAYABLE else "blocked"
    if outcome.result == "verified":
        if outcome.new_version == "current":
            return "healed"
        if outcome.new_version == "pending_review":
            return "heal_pending"
        return "passed"
    return "outdated" if outcome.reason in DRIFT_REASONS else "blocked"


def is_drift(outcome: ReplayOutcome) -> bool:
    """A failure worth replaying once more before it counts (D7). Environment failures aren't: replaying
    right after a rate limit or a CAPTCHA makes it worse."""
    return outcome.result == "failed" and outcome.reason in DRIFT_REASONS
