"""
OpenAI provider — wraps the official openai SDK.
"""


class OpenAIProvider:
    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str, model: str = ""):
        try:
            import openai as _openai
        except ImportError:
            raise ImportError("openai package is required: uv add openai")
        self._client = _openai.AsyncOpenAI(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    async def chat(self, system: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            max_tokens=2048,
        )
        return response.choices[0].message.content
