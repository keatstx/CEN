"""LLM factory — creates the configured backend with graceful fallback."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from cen.llm.mock import MockLanguageModel

if TYPE_CHECKING:
    from cen.config import Settings
    from cen.llm.base import LanguageModel

logger = structlog.get_logger()


class FallbackLanguageModel:
    """Wraps a primary LLM and falls back to mock on timeout or error."""

    def __init__(self, primary: LanguageModel, fallback: LanguageModel, timeout: float):
        self._primary = primary
        self._fallback = fallback
        self._timeout = timeout

    @property
    def backend_name(self) -> str:
        return self._primary.backend_name

    @property
    def fallback_name(self) -> str:
        return self._fallback.backend_name

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        try:
            return await asyncio.wait_for(
                self._primary.generate(prompt, max_tokens),
                timeout=self._timeout,
            )
        except (asyncio.TimeoutError, Exception) as exc:
            await logger.awarning(
                "llm_fallback_triggered",
                primary=self._primary.backend_name,
                error=str(exc),
            )
            return await self._fallback.generate(prompt, max_tokens)

    async def is_available(self) -> bool:
        return await self._primary.is_available()


def create_language_model(settings: Settings) -> FallbackLanguageModel:
    """Build the LLM stack based on settings."""
    mock = MockLanguageModel()

    if settings.llm_backend == "gguf":
        from cen.llm.gguf import GGUFLanguageModel

        primary: LanguageModel = GGUFLanguageModel(settings.gguf_model_path)
    elif settings.llm_backend == "api":
        from cen.llm.openai_compat import OpenAICompatLanguageModel

        primary = OpenAICompatLanguageModel(
            base_url=settings.llm_api_base,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout,
        )
    else:
        primary = mock

    return FallbackLanguageModel(
        primary=primary,
        fallback=mock,
        timeout=settings.llm_timeout,
    )
