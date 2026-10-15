"""Deterministic denylist, benign allowlist, and Gitea destructive baseline rules."""

import re
from typing import Final

from app.policy.models import ActionContext, RiskAssessment, RiskLevel

DENYLIST_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"delete", "purchase", "transfer", "publish", "send", "reset", "security"}
)

_DENYLIST_REGEX: Final[dict[str, re.Pattern[str]]] = {
    "delete": re.compile(r"\b(delete|deletes|deleting|deleted|drop|truncate|purge)\b", re.IGNORECASE),
    "purchase": re.compile(
        r"\b(purchase|purchases|purchasing|purchased|buy|checkout|pay|charge)\b", re.IGNORECASE
    ),
    "transfer": re.compile(r"\b(transfer|transfers|transferring|transferred)\b", re.IGNORECASE),
    "publish": re.compile(r"\b(publish|publishes|publishing|published)\b", re.IGNORECASE),
    "send": re.compile(r"\b(send|sends|sending|sent)\b", re.IGNORECASE),
    "reset": re.compile(r"\b(reset|resets|resetting)\b", re.IGNORECASE),
    "security": re.compile(
        r"\b(security|password|passwords|token|tokens|credential|credentials|revoke|revoking|revoked"
        r"|ssh[\s_-]?key|gpg[\s_-]?key|2fa|mfa)\b",
        re.IGNORECASE,
    ),
}

_AMBIGUOUS_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"\b(draft|drafts|unsaved)\b", re.IGNORECASE),
    re.compile(r"\b(zoom|filter|filters|view|search|selection)\b", re.IGNORECASE),
    re.compile(r"\b(feedback|ping|test[\s_-]?message)\b", re.IGNORECASE),
    re.compile(r"\b(preview|sample)\b", re.IGNORECASE),
]

_BENIGN_EXACT_NAMES: Final[frozenset[str]] = frozenset(
    {"cancel", "no", "unwatch", "dismiss", "close modal", "back"}
)


def match_denylist_keywords(text: str) -> list[str]:
    """Find all matching denylist keywords in the provided text."""
    matched: list[str] = []
    for kw, regex in _DENYLIST_REGEX.items():
        if regex.search(text):
            matched.append(kw)
    return matched


def is_benign(name: str, role: str, url: str) -> RiskAssessment | None:
    """Check if the action is explicitly benign despite containing potential keyword tokens."""
    low_name = name.strip().lower()
    low_url = url.strip().lower()

    if low_name in _BENIGN_EXACT_NAMES:
        return RiskAssessment(
            level=RiskLevel.LOW,
            reason=f"Benign UI control: '{name}'",
            flagged_by="fast_path",
            confidence=1.0,
            matched_rule="benign_control",
        )

    # Documentation and help links (e.g., "How do I mirror repositories?")
    if (
        "how do i" in low_name
        or "documentation" in low_name
        or "help" in low_name
        or "docs" in low_name
        or "guide" in low_name
    ) and role in ("link", "button"):
        return RiskAssessment(
            level=RiskLevel.LOW,
            reason=f"Informational link or documentation: '{name}'",
            flagged_by="fast_path",
            confidence=1.0,
            matched_rule="benign_docs_link",
        )

    # File drop zone ("Drop files or click here to upload.")
    if "drop files" in low_name or "click here to upload" in low_name:
        return RiskAssessment(
            level=RiskLevel.LOW,
            reason="File upload area drop-zone",
            flagged_by="fast_path",
            confidence=1.0,
            matched_rule="benign_drop_zone",
        )

    # Dashboard filter tab "Private" (e.g. at "/")
    if (
        low_name == "private"
        and (low_url == "/" or "/explore" in low_url or "dashboard" in low_url)
        and role in ("link", "tab", "menuitem")
    ):
        return RiskAssessment(
            level=RiskLevel.LOW,
            reason="Dashboard filter for private items",
            flagged_by="fast_path",
            confidence=1.0,
            matched_rule="benign_filter_tab",
        )

    return None


def is_ambiguous(action_text: str, context: ActionContext | None = None) -> bool:
    """Check whether the action has ambiguous scope requiring LLM disambiguation."""
    low_text = action_text.strip().lower()

    # Generic confirmation without clear deterministic context
    if low_text in ("yes", "confirm", "ok", "continue", "proceed") and (
        not context or (not context.dialog_text and not context.aria_excerpt and not context.previous_step)
    ):
        return True

    # Ambiguity only applies if a denylist keyword is actually matched in the action
    if not match_denylist_keywords(low_text):
        return False

    # Denylist keywords combined with temporary/local targets like "draft", "zoom", "filter"
    return any(pattern.search(low_text) for pattern in _AMBIGUOUS_PATTERNS)


def check_gitea_baseline(
    name: str,
    role: str,
    url: str,
    context: ActionContext | None = None,
) -> RiskAssessment | None:
    """Evaluate against agreed Gitea destructive baseline actions."""
    low_name = name.strip().lower()
    low_url = url.strip().lower()
    ctx_parts: list[str] = []
    if context:
        if context.title:
            ctx_parts.append(context.title)
        if context.aria_excerpt:
            ctx_parts.append(context.aria_excerpt)
        if context.dialog_text:
            ctx_parts.append(context.dialog_text)
        if context.previous_step:
            ctx_parts.append(context.previous_step)
    ctx_text = " ".join(ctx_parts).lower()

    # 1. Generic confirmation buttons ("Yes", "Confirm", "OK", "Continue")
    if low_name in ("yes", "ok", "confirm", "continue"):
        destructive_signals = [
            "delete branch",
            "cannot be undone",
            "delete repository",
            "delete wiki",
            "archive this repo",
            "archive repo",
            "remove webhook",
            "delete label",
            "delete milestone",
            "delete comment",
            "delete this issue",
            "permanently",
            "delete",
        ]
        if any(sig in ctx_text for sig in destructive_signals):
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reason=f"Confirmation inherits destructive dialog risk ({name})",
                flagged_by="denylist",
                confidence=1.0,
                matched_rule="gitea_dialog_confirm_destructive",
            )

    # 2. High Risk Gitea Destructive Actions
    # Repository deletion / transfer / wiki / archive
    if "delete this repository" in low_name or "delete repository" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Irreversible repository deletion",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_delete_repository",
        )

    if "transfer ownership" in low_name or "perform transfer" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Transferring repository ownership to another user or organisation",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_transfer_ownership",
        )

    if "delete wiki data" in low_name or "purge wiki" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Permanent deletion of wiki data",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_delete_wiki",
        )

    if "archive repo" in low_name or "archive this repo" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Archiving repository makes it read-only",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_archive_repo",
        )

    # Visibility change / private repository setting
    if "make repository private" in low_name or ("private" in low_name and role == "checkbox"):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Repository visibility and security change",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_visibility_change",
        )

    # Push mirror: pushes code to external remote (data egress)
    if "add push mirror" in low_name or "push mirror" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Push mirror transmits codebase to an external remote",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_push_mirror",
        )

    # Avatar deletion
    if "delete current avatar" in low_name or "delete avatar" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Deletion of profile or repository avatar",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_delete_avatar",
        )

    # Branch deletion
    if "delete branch" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Permanent deletion of git branch",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_delete_branch",
        )

    # Release deletion
    if "delete release" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Permanent deletion of published release",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_delete_release",
        )

    # Webhook removal
    if "remove webhook" in low_name or "delete webhook" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Deletion of webhook integration",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_remove_webhook",
        )

    # SSH / GPG Key Revocation
    if (
        "revoke" in low_name or "delete" in low_name
    ) and ("ssh" in low_name or "gpg" in low_name or "key" in low_name):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Revocation or deletion of SSH / GPG authentication keys (security)",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_security_revoke_key",
        )

    # User / account security changes
    if "update password" in low_name or "change password" in low_name:
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Account security credential change",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_update_password",
        )

    if low_name == "block" and ("/issues" in low_url or role in ("button", "menuitem")):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Blocking user access",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_block_user",
        )

    # Route-contextual bare "Delete" links
    if low_name == "delete":
        if "/labels" in low_url:
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reason="Deletion of repository label",
                flagged_by="denylist",
                confidence=1.0,
                matched_rule="gitea_delete_label",
            )
        if "/milestones" in low_url:
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reason="Deletion of repository milestone",
                flagged_by="denylist",
                confidence=1.0,
                matched_rule="gitea_delete_milestone",
            )
        if "/issues" in low_url:
            return RiskAssessment(
                level=RiskLevel.HIGH,
                reason="Deletion of issue or comment",
                flagged_by="denylist",
                confidence=1.0,
                matched_rule="gitea_delete_comment",
            )

    # 3. Medium Risk Actions (reversible state changes / session operations)
    if "close issue" in low_name or (low_name == "close" and "/issues" in low_url):
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="Reversible state change: closing issue",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_close_issue",
        )

    if "lock conversation" in low_name:
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="Reversible state change: locking conversation",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_lock_conversation",
        )

    if "close milestone" in low_name or (low_name == "close" and "/milestones" in low_url):
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="Reversible state change: closing milestone",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_close_milestone",
        )

    if "rename branch" in low_name:
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="Renaming branch changes references but preserves git history",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_rename_branch",
        )

    if "sign out" in low_name or "logout" in low_name or "log out" in low_name:
        return RiskAssessment(
            level=RiskLevel.MEDIUM,
            reason="Session termination ends the current agent run",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_sign_out",
        )

    return None
