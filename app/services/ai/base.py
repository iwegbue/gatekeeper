"""
AI Provider protocol — the interface all providers must implement.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class AIProvider(Protocol):
    """Minimal chat interface for all AI providers."""

    async def chat(self, system: str, messages: list[dict]) -> str:
        """
        Send a chat request and return the assistant's text response.

        Args:
            system: System prompt string.
            messages: List of {"role": "user"|"assistant", "content": str} dicts.

        Returns:
            The assistant's text response as a string.
        """
        ...

    @property
    def model(self) -> str:
        """Return the model identifier being used."""
        ...
