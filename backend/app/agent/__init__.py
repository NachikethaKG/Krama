"""Browser execution: a headless Playwright session and an executor for the contract's action types."""

from app.agent.session import PlaywrightSession, SessionConfig

__all__ = ["PlaywrightSession", "SessionConfig"]
