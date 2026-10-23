"""GitHub-specific danger-zone, secret, and branch deletion safety rules."""

from __future__ import annotations

import re
from typing import Final

try:
    from app.policy.models import RiskLevel, StepRiskAssessment
except ImportError:  # pragma: no cover
    from backend.app.policy.models import (  # type: ignore[import-not-found,no-redef]
        RiskLevel,
        StepRiskAssessment,
    )

__all__ = [
    "BRANCH_DELETE_SELECTOR_RE",
    "GITHUB_DESTRUCTIVE_PHRASES",
    "evaluate_github_danger_zone",
]

GITHUB_DESTRUCTIVE_PHRASES: Final[set[str]] = {
    "delete this repository",
    "delete repository",
    "change visibility",
    "make public",
    "make private",
    "transfer ownership",
    "archive this repository",
    "delete branch",
    "delete this branch",
    "revoke",
}

BRANCH_DELETE_SELECTOR_RE: Final[re.Pattern[str]] = re.compile(
    r"(branch-delete-dialog|delete.*branch|form\[action[\*~|\^$]?=['\"]?/branches/delete)",
    re.IGNORECASE,
)


def evaluate_github_danger_zone(
    url: str,
    target_selector: str | None = None,
    action_text: str | None = None,
) -> StepRiskAssessment:
    clean_url = (url or "").lower()
    clean_text = (action_text or "").strip().lower()
    clean_selector = (target_selector or "").strip().lower()

    # 1. Repository settings danger zone & visibility
    if "/settings" in clean_url:
        if "/settings/keys" in clean_url and any(
            verb in clean_text or verb in clean_selector
            for verb in ["add", "new key", "delete", "revoke", "deploy key", "key"]
        ):
            return StepRiskAssessment(
                risk_level=RiskLevel.HIGH,
                reason="GitHub Deploy Key modification detected",
                requires_confirmation=True,
            )
        if "/settings/secrets" in clean_url:
            return StepRiskAssessment(
                risk_level=RiskLevel.HIGH,
                reason="GitHub Secrets access or modification detected",
                requires_confirmation=True,
            )
        if any(phrase in clean_text for phrase in GITHUB_DESTRUCTIVE_PHRASES) or any(
            phrase in clean_selector for phrase in GITHUB_DESTRUCTIVE_PHRASES
        ):
            return StepRiskAssessment(
                risk_level=RiskLevel.HIGH,
                reason=f"GitHub Settings danger-zone action detected: '{clean_text or clean_selector}'",
                requires_confirmation=True,
            )

    # 2. Narrowed /branches rule: only flag destructive deletion/rename actions
    if "/branches" in clean_url:
        is_delete_btn = any(w in clean_text for w in ["delete", "destroy", "trash"])
        is_delete_selector = bool(BRANCH_DELETE_SELECTOR_RE.search(clean_selector))
        if is_delete_btn or is_delete_selector:
            return StepRiskAssessment(
                risk_level=RiskLevel.HIGH,
                reason="GitHub branch deletion control targeted",
                requires_confirmation=True,
            )

    # 3. Direct destructive branch or repository deletion targeting across GitHub
    if any(
        phrase in clean_text
        for phrase in ("delete branch", "delete this branch", "delete this repository", "delete repository")
    ) or bool(BRANCH_DELETE_SELECTOR_RE.search(clean_selector)):
        return StepRiskAssessment(
            risk_level=RiskLevel.HIGH,
            reason=f"GitHub destructive action detected: '{clean_text or clean_selector}'",
            requires_confirmation=True,
        )

    return StepRiskAssessment(
        risk_level=RiskLevel.LOW,
        reason="Action evaluated as safe",
        requires_confirmation=False,
    )
