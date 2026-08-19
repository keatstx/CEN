"""Tests for LLM factory and fallback behavior."""

from __future__ import annotations

import asyncio

import pytest

from cen.config import Settings
from cen.llm.factory import FallbackLanguageModel, create_language_model
from cen.llm.mock import MockLanguageModel


class TestMockLanguageModel:
    async def test_generate_income(self):
        llm = MockLanguageModel()
        result = await llm.generate("What about FPL income?")
        assert "income" in result.lower() or "fpl" in result.lower()

    async def test_generate_generic(self):
        llm = MockLanguageModel()
        result = await llm.generate("hello world")
        assert "Processed request" in result

    async def test_is_available(self):
        llm = MockLanguageModel()
        assert await llm.is_available() is True


class TestFallbackLanguageModel:
    async def test_falls_back_on_error(self):
        class FailingLLM:
            backend_name = "failing"

            async def generate(self, prompt: str, max_tokens: int = 128) -> str:
                raise RuntimeError("boom")

            async def is_available(self) -> bool:
                return False

        mock = MockLanguageModel()
        fallback = FallbackLanguageModel(FailingLLM(), mock, timeout=1.0)
        result = await fallback.generate("test income prompt")
        assert len(result) > 0  # Should get mock response

    async def test_falls_back_on_timeout(self):
        class SlowLLM:
            backend_name = "slow"

            async def generate(self, prompt: str, max_tokens: int = 128) -> str:
                await asyncio.sleep(10)
                return "should not reach"

            async def is_available(self) -> bool:
                return True

        mock = MockLanguageModel()
        fallback = FallbackLanguageModel(SlowLLM(), mock, timeout=0.1)
        result = await fallback.generate("hello")
        assert "Processed request" in result


class TestCreateLanguageModel:
    def test_mock_backend(self):
        settings = Settings(llm_backend="mock")
        llm = create_language_model(settings)
        assert llm.backend_name == "mock-tlm-v1"


class TestDegradedReporting:
    """generate_checked must tell callers when the mock answered.

    Regression guard for the 2026-08-16 Groq retirement: the primary
    raised on every call, the mock's canned text was returned, and the
    concierge presented it as `llm_synthesis`.
    """

    class _Failing:
        backend_name = "openai-compat"

        async def generate(self, prompt: str, max_tokens: int = 128) -> str:
            raise RuntimeError("model_decommissioned")

        async def is_available(self) -> bool:
            return True

    class _Working:
        backend_name = "openai-compat"

        async def generate(self, prompt: str, max_tokens: int = 128) -> str:
            return "real model output"

        async def is_available(self) -> bool:
            return True

    async def test_flags_degraded_when_primary_fails(self):
        llm = FallbackLanguageModel(
            primary=self._Failing(), fallback=MockLanguageModel(), timeout=5.0
        )

        result = await llm.generate_checked("What about FPL income?")

        assert result.degraded is True
        assert "model_decommissioned" in (result.error or "")
        assert result.text  # user is still answered, never blocked

    async def test_not_degraded_on_success(self):
        llm = FallbackLanguageModel(
            primary=self._Working(), fallback=MockLanguageModel(), timeout=5.0
        )

        result = await llm.generate_checked("anything")

        assert result.degraded is False
        assert result.text == "real model output"
        assert result.error is None

    async def test_flags_degraded_on_timeout(self):
        class _Slow:
            backend_name = "openai-compat"

            async def generate(self, prompt: str, max_tokens: int = 128) -> str:
                await asyncio.sleep(1.0)
                return "too late"

            async def is_available(self) -> bool:
                return True

        llm = FallbackLanguageModel(
            primary=_Slow(), fallback=MockLanguageModel(), timeout=0.01
        )

        result = await llm.generate_checked("anything")

        assert result.degraded is True

    async def test_generate_still_returns_plain_string(self):
        """Existing callers keep working unchanged."""
        llm = FallbackLanguageModel(
            primary=self._Working(), fallback=MockLanguageModel(), timeout=5.0
        )

        assert await llm.generate("anything") == "real model output"
