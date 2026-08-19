"""LLM factory — creates the configured backend with graceful fallback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import structlog

from cen.llm.mock import MockLanguageModel

if TYPE_CHECKING:
    from cen.config import Settings
    from cen.llm.base import LanguageModel

logger = structlog.get_logger()


@dataclass(frozen=True)
class LLMGeneration:
    """Result of a generate call, plus whether it degraded to the mock.

    Callers that must not present canned mock text as real model output
    (the concierge, chiefly) check ``degraded`` instead of trusting the
    returned string. ``generate()`` stays string-returning so existing
    callers are unaffected.
    """

    text: str
    degraded: bool
    error: Optional[str] = None


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

    @property
    def model(self) -> str:
        """The primary's resolved model, for health reporting."""
        return getattr(self._primary, "model", "") or ""

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        result = await self.generate_checked(prompt, max_tokens)
        return result.text

    async def generate_checked(
        self, prompt: str, max_tokens: int = 128
    ) -> LLMGeneration:
        """Generate, reporting whether the answer came from the fallback.

        A provider outage or a retired model id makes the primary raise;
        we still answer (the mock) so the user is never blocked, but the
        result is flagged so callers can decline to pass canned text off
        as model output.
        """
        try:
            text = await asyncio.wait_for(
                self._primary.generate(prompt, max_tokens),
                timeout=self._timeout,
            )
            return LLMGeneration(text=text, degraded=False)
        except Exception as exc:  # noqa: BLE001 - any failure degrades
            await logger.awarning(
                "llm_fallback_triggered",
                primary=self._primary.backend_name,
                error=str(exc),
            )
            text = await self._fallback.generate(prompt, max_tokens)
            return LLMGeneration(text=text, degraded=True, error=str(exc))

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
