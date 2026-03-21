"""
AI provider factory — selects and instantiates the correct provider
based on DB settings, with env var fallback for Anthropic.
"""
import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai.base import AIProvider


class AIConfigError(Exception):
    """Raised when AI cannot be configured (no key, wrong provider, etc.)"""
    pass


def configure(
    provider: str,
    anthropic_api_key: str = "",
    openai_api_key: str = "",
    ollama_base_url: str = "",
    model: str = "",
) -> "AIProvider":
    """
    Instantiate the correct provider from explicit config values.
    Falls back to ANTHROPIC_API_KEY env var if no Anthropic key given.

    Raises AIConfigError if the requested provider cannot be configured.
    """
    provider = (provider or "anthropic").lower()

    if provider == "anthropic":
        key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise AIConfigError(
                "Anthropic API key not configured. Set it in Settings or ANTHROPIC_API_KEY env var."
            )
        from app.services.ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=key, model=model)

    if provider == "openai":
        if not openai_api_key:
            raise AIConfigError("OpenAI API key not configured. Set it in Settings.")
        from app.services.ai.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=openai_api_key, model=model)

    if provider == "ollama":
        url = ollama_base_url or "http://localhost:11434"
        from app.services.ai.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=url, model=model)

    raise AIConfigError(f"Unknown AI provider: {provider!r}. Choose anthropic, openai, or ollama.")


async def get_provider_from_db(db) -> "AIProvider":
    """
    Load provider config from DB settings and return an AI provider.
    This is the primary entrypoint used by routers.
    """
    from app.services.settings_service import get_settings
    s = await get_settings(db)
    return configure(
        provider=s.ai_provider,
        anthropic_api_key=s.anthropic_api_key,
        openai_api_key=s.openai_api_key,
        ollama_base_url=s.ollama_base_url,
        model=s.ai_model,
    )
