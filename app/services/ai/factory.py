"""
AI provider factory — selects and instantiates the correct provider
based on DB settings, with env var fallback for Anthropic.
"""
import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse

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
        _validate_ollama_url(url)
        from app.services.ai.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=url, model=model)

    raise AIConfigError(f"Unknown AI provider: {provider!r}. Choose anthropic, openai, or ollama.")


# Allowed hostnames for the Ollama base URL (prevents SSRF to internal services)
_OLLAMA_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1", "ollama"}


def _validate_ollama_url(url: str) -> None:
    """Reject Ollama URLs that point to non-local hosts (SSRF prevention)."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except Exception:
        raise AIConfigError(f"Invalid Ollama base URL: {url!r}")

    if host not in _OLLAMA_ALLOWED_HOSTS:
        raise AIConfigError(
            f"Ollama base URL must point to a local host (got {host!r}). "
            f"Allowed: {sorted(_OLLAMA_ALLOWED_HOSTS)}"
        )


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
