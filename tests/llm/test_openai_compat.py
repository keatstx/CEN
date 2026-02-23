"""Tests for the OpenAI-compatible LLM backend."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cen.llm.openai_compat import OpenAICompatLanguageModel


@pytest.fixture
def model():
    return OpenAICompatLanguageModel(
        base_url="http://localhost:11434/v1",
        model="phi3:mini",
    )


FAKE_COMPLETION = {
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello from the API"},
        }
    ]
}

FAKE_REQUEST = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")


class TestGenerate:
    async def test_parses_response(self, model: OpenAICompatLanguageModel):
        mock_response = httpx.Response(200, json=FAKE_COMPLETION, request=FAKE_REQUEST)
        with patch.object(model._client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await model.generate("Say hello")
        assert result == "Hello from the API"

    async def test_sends_correct_payload(self, model: OpenAICompatLanguageModel):
        mock_response = httpx.Response(200, json=FAKE_COMPLETION, request=FAKE_REQUEST)
        mock_post = AsyncMock(return_value=mock_response)
        with patch.object(model._client, "post", mock_post):
            await model.generate("Say hello", max_tokens=64)
        mock_post.assert_called_once_with(
            "/chat/completions",
            json={
                "model": "phi3:mini",
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": 64,
            },
        )

    async def test_raises_on_error_status(self, model: OpenAICompatLanguageModel):
        mock_response = httpx.Response(500, json={"error": "boom"}, request=FAKE_REQUEST)
        with patch.object(model._client, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await model.generate("Say hello")


class TestIsAvailable:
    async def test_returns_true_when_reachable(self, model: OpenAICompatLanguageModel):
        mock_response = httpx.Response(200, json={"data": []})
        with patch.object(model._client, "get", new_callable=AsyncMock, return_value=mock_response):
            assert await model.is_available() is True

    async def test_returns_false_on_connection_error(self, model: OpenAICompatLanguageModel):
        with patch.object(
            model._client, "get", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")
        ):
            assert await model.is_available() is False


class TestBackendName:
    def test_backend_name(self, model: OpenAICompatLanguageModel):
        assert model.backend_name == "openai-compat"


class TestFactory:
    async def test_creates_openai_compat_backend(self):
        from cen.config import Settings
        from cen.llm.factory import create_language_model

        settings = Settings(llm_backend="api", llm_api_base="http://localhost:11434/v1")
        lm = create_language_model(settings)
        assert lm.backend_name == "openai-compat"
