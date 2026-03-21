"""
Anthropic provider — wraps the official anthropic SDK.
"""


class AnthropicProvider:
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str, model: str = ""):
        try:
            import anthropic as _anthropic
        except ImportError:
            raise ImportError("anthropic package is required: uv add anthropic")
        self._client = _anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    async def chat(self, system: str, messages: list[dict]) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=messages,
        )
        return response.content[0].text
