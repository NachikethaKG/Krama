"""LLM layer: one `LLMProvider` interface; Gemini for real runs, a replaying fake for tests."""

from app.config import Settings
from app.llm.base import (
    LLMAttempt,
    LLMError,
    LLMProvider,
    LLMRateLimitedError,
    LLMResult,
    LLMUnavailableError,
)
from app.llm.fake import FakeProvider, FakeResponse
from app.llm.gemini import DEFAULT_MODELS, GeminiProvider


def create_provider(settings: Settings) -> LLMProvider:
    """The provider selected by `LLM_PROVIDER` (`fake` or `gemini`)."""
    if settings.llm_provider == "gemini":
        return GeminiProvider(settings.gemini_api_key, DEFAULT_MODELS)
    return FakeProvider.from_dir()


__all__ = [
    "DEFAULT_MODELS",
    "FakeProvider",
    "FakeResponse",
    "GeminiProvider",
    "LLMAttempt",
    "LLMError",
    "LLMProvider",
    "LLMRateLimitedError",
    "LLMResult",
    "LLMUnavailableError",
    "create_provider",
]
