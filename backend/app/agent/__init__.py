"""Browser execution: a headless Playwright session and an executor for the contract's action types."""

from app.agent.executor import ActionError, ActionErrorCode, ActionExecutor, ActionResult
from app.agent.healer import ElementFingerprint, HealingResult, LocatorHealer, ScoredCandidate
from app.agent.quota import check_and_consume_gemini_heal_quota
from app.agent.session import PlaywrightSession, SessionConfig, open_start_page, page_snapshot

__all__ = [
    "ActionError",
    "ActionErrorCode",
    "ActionExecutor",
    "ActionResult",
    "ElementFingerprint",
    "HealingResult",
    "LocatorHealer",
    "PlaywrightSession",
    "ScoredCandidate",
    "SessionConfig",
    "check_and_consume_gemini_heal_quota",
    "open_start_page",
    "page_snapshot",
]
