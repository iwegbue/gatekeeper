"""
Ollama provider — calls the local Ollama /api/chat endpoint via httpx.
"""

import httpx


class OllamaProvider:
    DEFAULT_MODEL = "llama3"

    def __init__(self, base_url: str, model: str = ""):
        self._base_url = base_url.rstrip("/")
        self._model = model or self.DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    async def chat(self, system: str, messages: list[dict]) -> str:
        full_messages = [{"role": "system", "content": system}] + messages
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": full_messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
