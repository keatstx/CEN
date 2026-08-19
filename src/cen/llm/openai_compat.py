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

    @property
    def model(self) -> str:
        return self._model

    async def is_available(self) -> bool:
        """True only when the *configured model* is actually offered.

        Checking that /models returns 200 is not enough: it proves the
        key is valid and the host is reachable, both of which stay true
        after a provider retires the model we ask for. Groq shut down
        llama-3.3-70b-versatile on 2026-08-16 while /models kept
        answering 200, so every completion failed and silently degraded
        to the mock behind a green health check. Verify membership.

        Providers that don't enumerate models return an empty list; we
        treat reachability as available there rather than hard-failing.
        """
        try:
            response = await self._client.get("/models")
            if response.status_code != 200:
                return False
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return False
        entries = payload.get("data") if isinstance(payload, dict) else None
        if not entries:
            return True
        offered = {
            e.get("id") for e in entries if isinstance(e, dict) and e.get("id")
        }
        return not offered or self._model in offered
