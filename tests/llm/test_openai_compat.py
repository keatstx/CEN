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


class TestIsAvailableChecksModel:
    """/models returning 200 is not proof the configured model works.

    Groq retired llama-3.3-70b-versatile on 2026-08-16 while /models
    kept answering 200 for the surviving models, so a green health
    check masked a fully degraded LLM. Availability must mean "the
    model we ask for is offered".
    """

    def _model(self, model_id: str = "phi3:mini"):
        return OpenAICompatLanguageModel(
            base_url="http://localhost:11434/v1", model=model_id
        )

    def _models_response(self, ids):
        return httpx.Response(
            200,
            json={"data": [{"id": i} for i in ids]},
            request=httpx.Request("GET", "http://localhost:11434/v1/models"),
        )

    async def test_available_when_model_listed(self):
        model = self._model("phi3:mini")
        resp = self._models_response(["phi3:mini", "llama3"])
        with patch.object(model._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await model.is_available() is True

    async def test_unavailable_when_model_retired(self):
        model = self._model("llama-3.3-70b-versatile")
        resp = self._models_response(["openai/gpt-oss-120b", "qwen/qwen3.6-27b"])
        with patch.object(model._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await model.is_available() is False

    async def test_available_when_provider_does_not_enumerate(self):
        """Don't hard-fail providers that return no model list."""
        model = self._model()
        resp = httpx.Response(
            200,
            json={"data": []},
            request=httpx.Request("GET", "http://localhost:11434/v1/models"),
        )
        with patch.object(model._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await model.is_available() is True

    async def test_unavailable_on_non_200(self):
        model = self._model()
        resp = httpx.Response(
            401,
            json={"error": "bad key"},
            request=httpx.Request("GET", "http://localhost:11434/v1/models"),
        )
        with patch.object(model._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await model.is_available() is False

    async def test_unavailable_on_malformed_json(self):
        model = self._model()
        resp = httpx.Response(
            200,
            content=b"not json",
            request=httpx.Request("GET", "http://localhost:11434/v1/models"),
        )
        with patch.object(model._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await model.is_available() is False

    async def test_unavailable_on_transport_error(self):
        model = self._model()
        with patch.object(
            model._client, "get", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("no route"),
        ):
            assert await model.is_available() is False
