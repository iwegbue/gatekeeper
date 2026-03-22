"""
Tests for AI provider factory — selection, env fallback, config error.
"""

import os
from unittest.mock import patch

import pytest

from app.services.ai.factory import AIConfigError, configure

# ── configure() ────────────────────────────────────────────────────────────────


def test_configure_anthropic_with_key():
    provider = configure(provider="anthropic", anthropic_api_key="test-key-123")
    from app.services.ai.anthropic_provider import AnthropicProvider

    assert isinstance(provider, AnthropicProvider)
    assert provider.model  # has a default model


def test_configure_anthropic_uses_env_fallback():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key-abc"}):
        provider = configure(provider="anthropic", anthropic_api_key="")
    from app.services.ai.anthropic_provider import AnthropicProvider

    assert isinstance(provider, AnthropicProvider)


def test_configure_anthropic_no_key_raises():
    with patch.dict(os.environ, {}, clear=True):
        # Ensure ANTHROPIC_API_KEY is not set
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(AIConfigError, match="Anthropic API key"):
            configure(provider="anthropic", anthropic_api_key="")


def test_configure_openai_with_key():
    provider = configure(provider="openai", openai_api_key="openai-key-xyz")
    from app.services.ai.openai_provider import OpenAIProvider

    assert isinstance(provider, OpenAIProvider)


def test_configure_openai_no_key_raises():
    with pytest.raises(AIConfigError, match="OpenAI API key"):
        configure(provider="openai", openai_api_key="")


def test_configure_ollama_with_url():
    provider = configure(provider="ollama", ollama_base_url="http://localhost:11434")
    from app.services.ai.ollama_provider import OllamaProvider

    assert isinstance(provider, OllamaProvider)
    assert provider.model  # has a default model


def test_configure_ollama_uses_default_url():
    """Ollama defaults to localhost:11434 if no URL given."""
    provider = configure(provider="ollama", ollama_base_url="")
    from app.services.ai.ollama_provider import OllamaProvider

    assert isinstance(provider, OllamaProvider)


def test_configure_unknown_provider_raises():
    with pytest.raises(AIConfigError, match="Unknown AI provider"):
        configure(provider="magic_ai", anthropic_api_key="x")


def test_configure_custom_model():
    provider = configure(
        provider="anthropic",
        anthropic_api_key="test-key",
        model="claude-opus-4-6",
    )
    assert provider.model == "claude-opus-4-6"


def test_configure_anthropic_default_model():
    from app.services.ai.anthropic_provider import AnthropicProvider

    provider = configure(provider="anthropic", anthropic_api_key="test-key")
    assert provider.model == AnthropicProvider.DEFAULT_MODEL


def test_configure_openai_default_model():
    from app.services.ai.openai_provider import OpenAIProvider

    provider = configure(provider="openai", openai_api_key="test-key")
    assert provider.model == OpenAIProvider.DEFAULT_MODEL


def test_configure_ollama_default_model():
    from app.services.ai.ollama_provider import OllamaProvider

    provider = configure(provider="ollama")
    assert provider.model == OllamaProvider.DEFAULT_MODEL


def test_configure_case_insensitive_provider():
    """Provider name should be normalized to lowercase."""
    provider = configure(provider="Anthropic", anthropic_api_key="test-key")
    from app.services.ai.anthropic_provider import AnthropicProvider

    assert isinstance(provider, AnthropicProvider)


# ── get_provider_from_db ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_provider_from_db_anthropic(db):
    from app.services.ai.factory import get_provider_from_db
    from app.services.settings_service import update_settings

    await update_settings(db, ai_provider="anthropic", anthropic_api_key="db-test-key")
    provider = await get_provider_from_db(db)
    from app.services.ai.anthropic_provider import AnthropicProvider

    assert isinstance(provider, AnthropicProvider)


@pytest.mark.asyncio
async def test_get_provider_from_db_ollama(db):
    from app.services.ai.factory import get_provider_from_db
    from app.services.settings_service import update_settings

    await update_settings(db, ai_provider="ollama", ollama_base_url="http://localhost:11434")
    provider = await get_provider_from_db(db)
    from app.services.ai.ollama_provider import OllamaProvider

    assert isinstance(provider, OllamaProvider)


@pytest.mark.asyncio
async def test_get_provider_from_db_raises_without_key(db):
    from app.services.ai.factory import AIConfigError, get_provider_from_db
    from app.services.settings_service import update_settings

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        await update_settings(db, ai_provider="anthropic", anthropic_api_key="")
        with pytest.raises(AIConfigError):
            await get_provider_from_db(db)
