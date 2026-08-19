"""Model preference resolution — surviving provider retirements.

Regression suite for the 2026-08-16 Groq retirement of
llama-3.3-70b-versatile: a single pinned model id with no second
choice meant every completion failed until a human redeployed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cen.llm.model_resolver import choose_model, parse_preferences
from cen.llm.openai_compat import OpenAICompatLanguageModel


class TestParsePreferences:
    def test_single_model_still_works(self):
        """Existing single-id configuration must be untouched."""
        assert parse_preferences("phi3:mini") == ["phi3:mini"]

    def test_comma_separated_list_keeps_order(self):
        assert parse_preferences("a,b,c") == ["a", "b", "c"]

    def test_strips_whitespace(self):
        assert parse_preferences(" a , b ") == ["a", "b"]

    def test_drops_duplicates_keeping_first_position(self):
        assert parse_preferences("a,b,a") == ["a", "b"]

    def test_drops_empty_entries(self):
        assert parse_preferences("a,,b,") == ["a", "b"]

    def test_empty_string(self):
        assert parse_preferences("") == []


class TestChooseModel:
    def test_prefers_the_top_choice_when_offered(self):
        assert choose_model(["a", "b"], ["a", "b", "c"]) == "a"

    def test_steps_down_when_top_choice_retired(self):
        """The exact scenario: first preference no longer exists."""
        assert choose_model(["a", "b"], ["b", "c"]) == "b"

    def test_returns_none_when_every_preference_retired(self):
        """Must be loud, not silently papered over."""
        assert choose_model(["a", "b"], ["x", "y"]) is None

    def test_uses_top_choice_when_provider_does_not_enumerate(self):
        """Some OpenAI-compatible servers return no model list."""
        assert choose_model(["a", "b"], []) == "a"
        assert choose_model(["a", "b"], None) == "a"

    def test_no_preferences_returns_none(self):
        assert choose_model([], ["a"]) is None


def _models_response(ids):
    return httpx.Response(
        200,
        json={"data": [{"id": i} for i in ids]},
        request=httpx.Request("GET", "http://x/v1/models"),
    )


def _completion(text="hi"):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"role": "assistant", "content": text}}]},
        request=httpx.Request("POST", "http://x/v1/chat/completions"),
    )


class TestBackendResolution:
    def _model(self, pref: str):
        return OpenAICompatLanguageModel(base_url="http://x/v1", model=pref)

    async def test_resolves_top_choice(self):
        llm = self._model("openai/gpt-oss-20b,openai/gpt-oss-120b")
        resp = _models_response(["openai/gpt-oss-20b", "openai/gpt-oss-120b"])

        with patch.object(llm._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await llm.resolve() == "openai/gpt-oss-20b"
        assert llm.model == "openai/gpt-oss-20b"

    async def test_steps_down_when_top_choice_is_retired(self):
        llm = self._model("openai/gpt-oss-20b,openai/gpt-oss-120b")
        resp = _models_response(["openai/gpt-oss-120b"])

        with patch.object(llm._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await llm.resolve() == "openai/gpt-oss-120b"

    async def test_unavailable_when_all_preferences_retired(self):
        llm = self._model("llama-3.3-70b-versatile")
        resp = _models_response(["openai/gpt-oss-20b"])

        with patch.object(llm._client, "get", new_callable=AsyncMock, return_value=resp):
            assert await llm.is_available() is False

    async def test_resolution_is_cached(self):
        """/models must not be hit on every generate."""
        llm = self._model("a,b")
        resp = _models_response(["a"])

        with patch.object(
            llm._client, "get", new_callable=AsyncMock, return_value=resp
        ) as get:
            await llm.resolve()
            await llm.resolve()
            await llm.resolve()

        assert get.await_count == 1

    async def test_generate_uses_the_resolved_model(self):
        llm = self._model("a,b")
        get = AsyncMock(return_value=_models_response(["b"]))
        post = AsyncMock(return_value=_completion("from b"))

        with patch.object(llm._client, "get", get), patch.object(llm._client, "post", post):
            assert await llm.generate("hello") == "from b"

        assert post.await_args.kwargs["json"]["model"] == "b"

    async def test_generate_reresolves_after_a_model_error(self):
        """A retirement mid-process costs one failed call, not all of them."""
        llm = self._model("a,b")
        # First /models says "a" exists; after the failure it's gone.
        get = AsyncMock(
            side_effect=[_models_response(["a", "b"]), _models_response(["b"])]
        )
        dead = httpx.Response(
            400,
            json={"error": {"code": "model_decommissioned"}},
            request=httpx.Request("POST", "http://x/v1/chat/completions"),
        )
        post = AsyncMock(side_effect=[dead, _completion("from b")])

        with patch.object(llm._client, "get", get), patch.object(llm._client, "post", post):
            assert await llm.generate("hello") == "from b"

        assert llm.model == "b"
        assert post.await_count == 2

    async def test_generate_raises_when_nothing_is_offered(self):
        llm = self._model("retired-model")
        get = AsyncMock(return_value=_models_response(["something-else"]))

        with patch.object(llm._client, "get", get):
            with pytest.raises(RuntimeError, match="no configured model"):
                await llm.generate("hello")

    async def test_transient_network_failure_keeps_cached_choice(self):
        """Don't discard a good resolution over one flaky request."""
        llm = self._model("a,b")

        with patch.object(
            llm._client, "get", new_callable=AsyncMock,
            return_value=_models_response(["a"]),
        ):
            assert await llm.resolve() == "a"

        with patch.object(
            llm._client, "get", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("no route"),
        ):
            assert await llm.resolve(force=True) == "a"

    async def test_single_model_config_is_unchanged(self):
        """Backward compatibility with a plain model id."""
        llm = self._model("phi3:mini")

        with patch.object(
            llm._client, "get", new_callable=AsyncMock,
            return_value=_models_response(["phi3:mini"]),
        ):
            assert await llm.resolve() == "phi3:mini"


class TestDiscoveryFailureDoesNotBlockGeneration:
    """/models is a discovery endpoint, not a gate.

    An early version of the resolver required a successful /models read
    before every generate, which turned a flaky (or simply absent)
    discovery endpoint into a total outage — the opposite of the point.
    Generation is optimistic; health reporting stays strict.
    """

    def _model(self, pref="a,b"):
        return OpenAICompatLanguageModel(base_url="http://x/v1", model=pref)

    async def test_generate_proceeds_when_models_is_unreachable(self):
        llm = self._model()
        get = AsyncMock(side_effect=httpx.ConnectError("no route"))
        post = AsyncMock(return_value=_completion("worked anyway"))

        with patch.object(llm._client, "get", get), patch.object(llm._client, "post", post):
            assert await llm.generate("hello") == "worked anyway"

        # Falls back to the top preference and lets the call be the test.
        assert post.await_args.kwargs["json"]["model"] == "a"

    async def test_generate_proceeds_when_models_returns_non_200(self):
        llm = self._model()
        get = AsyncMock(
            return_value=httpx.Response(
                404, request=httpx.Request("GET", "http://x/v1/models")
            )
        )
        post = AsyncMock(return_value=_completion("ok"))

        with patch.object(llm._client, "get", get), patch.object(llm._client, "post", post):
            assert await llm.generate("hello") == "ok"

    async def test_health_is_strict_when_models_is_unreachable(self):
        """Optimistic generation must not leak into an optimistic /ready."""
        llm = self._model()

        with patch.object(
            llm._client, "get", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("no route"),
        ):
            assert await llm.is_available() is False


class TestProviderErrorBodyIsSurfaced:
    """A bare status line is not a diagnosis.

    Prod returned "403 Forbidden" with no indication whether the account
    was restricted, the key lacked entitlement to the model, or the
    request shape was rejected — three very different fixes.
    """

    async def test_error_body_is_included(self):
        llm = OpenAICompatLanguageModel(base_url="http://x/v1", model="a")
        forbidden = httpx.Response(
            403,
            json={"error": {"message": "Organization has been restricted"}},
            request=httpx.Request("POST", "http://x/v1/chat/completions"),
        )

        with patch.object(
            llm._client, "get", new_callable=AsyncMock,
            return_value=_models_response(["a"]),
        ), patch.object(
            llm._client, "post", new_callable=AsyncMock, return_value=forbidden
        ):
            with pytest.raises(httpx.HTTPStatusError, match="Organization has been restricted"):
                await llm.generate("hello")
