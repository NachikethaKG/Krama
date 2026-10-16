"""Deterministic denylist, benign allowlist, and Gitea destructive baseline rules.

Everything here matches on the *target control* (its role and accessible name), the page route and the
instruction's own words, never on the value an action types: a fill of "Delete old docs" into an issue title
is not a delete. Callers strip the typed value before matching (see `risk.check_action`).
"""

import re
from typing import Final

from app.policy.models import RiskAssessment, RiskLevel

DENYLIST_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"delete", "remove", "regenerate", "purchase", "transfer", "publish", "send", "reset", "security"}
)

# Keywords a deterministic heuristic may treat as harmless in an ambiguous scope ("Send feedback",
# "Reset filter"). Every other keyword is a hard destructive verb: without a real LLM verdict it never drops
# below HIGH.
SOFT_KEYWORDS: Final[frozenset[str]] = frozenset({"send", "reset"})

_DENYLIST_REGEX: Final[dict[str, re.Pattern[str]]] = {
    "delete": re.compile(r"\b(delete|deletes|deleting|deleted|drop|truncate|purge)\b", re.IGNORECASE),
    "remove": re.compile(
        r"\b(remove|removes|removing|removed|destroy|destroys|erase|erases|wipe|wipes)\b", re.IGNORECASE
    ),
    "regenerate": re.compile(r"\b(regenerate|regenerates|regenerating|regenerated)\b", re.IGNORECASE),
    "purchase": re.compile(
        r"\b(purchase|purchases|purchasing|purchased|buy|checkout|pay|charge)\b", re.IGNORECASE
    ),
    "transfer": re.compile(r"\b(transfer|transfers|transferring|transferred)\b", re.IGNORECASE),
    "publish": re.compile(r"\b(publish|publishes|publishing|published)\b", re.IGNORECASE),
    "send": re.compile(r"\b(send|sends|sending|sent)\b", re.IGNORECASE),
    "reset": re.compile(r"\b(reset|resets|resetting)\b", re.IGNORECASE),
    "security": re.compile(
        r"\b(security|password|passwords|token|tokens|credential|credentials|revoke|revokes|revoking|revoked"
        r"|secret|secrets|ssh[\s_-]?key|gpg[\s_-]?key|deploy[\s_-]?key|2fa|mfa)\b",
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

# Generic confirmation buttons. They carry no meaning of their own: they inherit the risk of the dialog text
# just before them, and are HIGH when that text can't be found.
GENERIC_CONFIRM_NAMES: Final[frozenset[str]] = frozenset({"yes", "ok", "confirm", "continue", "proceed"})

# Phrases in a dialog that make its generic confirm destructive, besides the denylist verbs themselves.
_DESTRUCTIVE_DIALOG_PHRASES: Final[tuple[str, ...]] = (
    "cannot be undone",
    "can not be undone",
    "permanently",
    "irreversible",
    "archive this repo",
    "archive repo",
)

# Visibility controls: "Make repository private", a "Visibility" select, "Change Visibility", "Make Public".
_VISIBILITY_NAME: Final[re.Pattern[str]] = re.compile(
    r"\b(private|public|visibility|visible)\b", re.IGNORECASE
)
_VISIBILITY_TOGGLE_ROLES: Final[frozenset[str]] = frozenset(
    {"checkbox", "switch", "radio", "combobox", "listbox", "option", "menuitemcheckbox", "menuitemradio"}
)
_VISIBILITY_CHANGE: Final[re.Pattern[str]] = re.compile(
    r"\b(make|change|set|switch|update)\b.*\b(private|public|visibility)\b", re.IGNORECASE
)


def match_denylist_keywords(text: str) -> list[str]:
    """Find all matching denylist keywords in the provided text."""
    matched: list[str] = []
    for kw, regex in _DENYLIST_REGEX.items():
        if regex.search(text):
            matched.append(kw)
    return matched


def hard_destructive_keywords(text: str) -> list[str]:
    """Denylist keywords in `text` that a heuristic may never downgrade (everything but SOFT_KEYWORDS)."""
    return [kw for kw in match_denylist_keywords(text) if kw not in SOFT_KEYWORDS]


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

    # Documentation and help links (e.g., "How do I mirror repositories?"). Not when a destructive verb is
    # on the control itself: "Delete docs" or "Delete guide page" deletes something.
    if (
        (
            "how do i" in low_name
            or "documentation" in low_name
            or "help" in low_name
            or "docs" in low_name
            or "guide" in low_name
        )
        and role in ("link", "button")
        and not match_denylist_keywords(low_name)
    ):
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


def is_ambiguous(action_text: str) -> bool:
    """A denylist verb with a temporary or local scope ("delete draft", "reset filter"): ask the LLM.

    Generic confirmations ("Yes", "OK") are not handled here: `risk.check_action` resolves them from the
    dialog text before the button and treats them as HIGH when there is none.
    """
    if not match_denylist_keywords(action_text):
        return False
    return any(pattern.search(action_text) for pattern in _AMBIGUOUS_PATTERNS)


def is_destructive_dialog_text(text: str) -> bool:
    """Whether the text of a confirmation dialog describes a destructive change."""
    low = text.lower()
    if any(phrase in low for phrase in _DESTRUCTIVE_DIALOG_PHRASES):
        return True
    if "archive" in low or "block" in low:
        return True
    return bool(match_denylist_keywords(low)) or _VISIBILITY_CHANGE.search(low) is not None


def check_gitea_baseline(name: str, role: str, url: str) -> RiskAssessment | None:
    """Evaluate the target control (role, name) on its route against the agreed Gitea baseline."""
    low_name = name.strip().lower()
    low_role = role.strip().lower()
    low_url = url.strip().lower()

    # 1. High Risk Gitea Destructive Actions
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

    # Visibility change: the "Make repository private" checkbox, a visibility select or radio, or a
    # "Change Visibility" / "Make Public" button, in either direction.
    if (
        low_role in _VISIBILITY_TOGGLE_ROLES and _VISIBILITY_NAME.search(low_name)
    ) or _VISIBILITY_CHANGE.search(low_name):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Repository visibility and security change",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_visibility_change",
        )

    # Push mirror: pushes code to external remote (data egress)
    if "push mirror" in low_name:
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

    # SSH / GPG / deploy key revocation
    if re.search(r"\b(revoke|delete|remove)\b", low_name) and re.search(
        r"\b(ssh|gpg|deploy|keys?)\b", low_name
    ):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Revocation or deletion of SSH / GPG authentication keys (security)",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_security_revoke_key",
        )

    # Collaborators and organisation members
    if re.search(r"\b(remove|delete)\b", low_name) and re.search(
        r"\b(collaborator|member|team)s?\b", low_name
    ):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Removing a user's access to the repository or organisation",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_remove_collaborator",
        )

    # OAuth2 application secrets
    if "regenerate" in low_name and ("secret" in low_name or "token" in low_name):
        return RiskAssessment(
            level=RiskLevel.HIGH,
            reason="Regenerating a secret invalidates the current one (security)",
            flagged_by="denylist",
            confidence=1.0,
            matched_rule="gitea_regenerate_secret",
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

    if low_name == "block" and ("/issues" in low_url or low_role in ("button", "menuitem")):
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

    # 2. Medium Risk Actions (reversible state changes / session operations)
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
