"""OpenAI-compatible HTTP backend for any /v1/chat/completions provider."""

from __future__ import annotations

import httpx


class OpenAICompatLanguageModel:
    """Talks to any OpenAI-compatible API (Ollama, vLLM, Groq, OpenAI, etc.)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    @property
    def backend_name(self) -> str:
        return "openai-compat"

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def is_available(self) -> bool:
        try:
            response = await self._client.get("/models")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
