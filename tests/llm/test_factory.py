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
