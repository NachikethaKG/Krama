"""LLM layer: one `LLMProvider` interface; Gemini for real runs, a replaying fake for tests, and an opt-in
local model (Ollama) for development (ADR 0010)."""

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
from app.llm.ollama import OllamaProvider
from app.llm.openai_compat import OpenAICompatProvider, SplitProvider
from app.llm.untrusted import UNTRUSTED_DATA_RULE, neutralize_tags, untrusted_block


def create_provider(settings: Settings) -> LLMProvider:
    """The provider selected by `LLM_PROVIDER` (`fake`, `gemini`, `ollama` or `groq`)."""
    if settings.llm_provider == "gemini":
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model_list or DEFAULT_MODELS)
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            settings.ollama_url,
            settings.ollama_model,
            timeout_s=settings.ollama_timeout_s,
            num_ctx=settings.ollama_num_ctx,
        )
    if settings.llm_provider == "groq":
        # Text on Groq; images (vision locator and verifier) on Gemini when a Gemini key is set.
        vision = (
            GeminiProvider(settings.gemini_api_key, settings.gemini_model_list or DEFAULT_MODELS)
            if settings.gemini_api_key
            else None
        )
        text = OpenAICompatProvider(settings.groq_url, settings.groq_api_key, settings.groq_model_list)
        return SplitProvider(text, vision)
    return FakeProvider.from_dir()


__all__ = [
    "DEFAULT_MODELS",
    "UNTRUSTED_DATA_RULE",
    "FakeProvider",
    "FakeResponse",
    "GeminiProvider",
    "LLMAttempt",
    "LLMError",
    "LLMProvider",
    "LLMRateLimitedError",
    "LLMResult",
    "LLMUnavailableError",
    "OllamaProvider",
    "OpenAICompatProvider",
    "SplitProvider",
    "create_provider",
    "neutralize_tags",
    "untrusted_block",
]
