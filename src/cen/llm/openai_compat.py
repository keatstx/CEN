"""OpenAI-compatible HTTP backend for any /v1/chat/completions provider."""

from __future__ import annotations

import asyncio
from typing import List, Optional, Set

import httpx
import structlog

from cen.llm.model_resolver import choose_model, parse_preferences

logger = structlog.get_logger()


class OpenAICompatLanguageModel:
    """Talks to any OpenAI-compatible API (Ollama, vLLM, Groq, OpenAI, etc.).

    ``model`` accepts a single id or a comma-separated preference list
    (see ``model_resolver``). The first preference the provider still
    offers is resolved lazily on first use, cached, and re-resolved
    after a failure — so a provider retiring the top choice costs one
    failed call, not an outage.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._preferences: List[str] = parse_preferences(model)
        # Resolved lazily: the constructor is sync and we must not do
        # network I/O here.
        self._resolved: Optional[str] = None
        self._resolve_lock = asyncio.Lock()
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

    @property
    def model(self) -> str:
        """The model in use — resolved if we've resolved, else top choice."""
        if self._resolved:
            return self._resolved
        return self._preferences[0] if self._preferences else ""

    @property
    def preferences(self) -> List[str]:
        return list(self._preferences)

    async def _offered(self) -> Optional[Set[str]]:
        """Model ids the provider reports, or None if we can't tell."""
        try:
            response = await self._client.get("/models")
            if response.status_code != 200:
                return None
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        entries = payload.get("data") if isinstance(payload, dict) else None
        if not entries:
            # Provider doesn't enumerate — reachable but unverifiable.
            return set()
        ids: Set[str] = set()
        for entry in entries:
            if isinstance(entry, dict):
                entry_id = entry.get("id")
                if isinstance(entry_id, str) and entry_id:
                    ids.add(entry_id)
        return ids

    @property
    def _top(self) -> Optional[str]:
        return self._preferences[0] if self._preferences else None

    async def _record(self, chosen: Optional[str], offered_count: int) -> None:
        if chosen is None:
            await logger.aerror(
                "llm_no_preferred_model_offered",
                preferences=self._preferences,
                offered_count=offered_count,
            )
        elif chosen != self._resolved:
            await logger.ainfo(
                "llm_model_resolved",
                model=chosen,
                preferences=self._preferences,
                # True when the top choice is gone and we stepped down.
                fallback=chosen != self._top,
            )
        self._resolved = chosen

    async def resolve(self, force: bool = False) -> Optional[str]:
        """Pick the highest-ranked preference the provider still offers.

        Cached: /models is hit once, not per generate. ``force`` clears
        the cache, which is what a failed completion does — that is how
        a mid-life retirement heals itself without a redeploy.

        Optimistic by design. If /models can't be read — transient
        network failure, or a provider that doesn't expose it at all —
        we fall back to the top preference and let the completion call
        itself be the test. Blocking generation on an unreadable
        *discovery* endpoint would turn a working provider into an
        outage, which is the opposite of the point.
        """
        if self._resolved and not force:
            return self._resolved
        async with self._resolve_lock:
            if self._resolved and not force:
                return self._resolved
            offered = await self._offered()
            if offered is None:
                return self._resolved or self._top
            chosen = choose_model(self._preferences, offered)
            await self._record(chosen, len(offered))
            return chosen

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        model = await self.resolve()
        if model is None:
            raise RuntimeError(
                "no configured model is offered by the provider: "
                f"{', '.join(self._preferences)}"
            )
        try:
            return await self._complete(model, prompt, max_tokens)
        except httpx.HTTPStatusError:
            # A 4xx here is usually "that model is gone". Re-resolve once
            # and retry, so a retirement mid-process costs one failed
            # call rather than every call until someone redeploys.
            retried = await self.resolve(force=True)
            if retried is None or retried == model:
                raise
            await logger.awarning(
                "llm_model_reresolved_after_failure",
                previous=model,
                model=retried,
            )
            return await self._complete(retried, prompt, max_tokens)

    async def _complete(self, model: str, prompt: str, max_tokens: int) -> str:
        response = await self._client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # The status line alone doesn't say *why*. Providers put the
            # actionable part in the body ("model_decommissioned",
            # "organization_restricted", an unsupported parameter), and
            # without it a 403 is indistinguishable from a 403.
            detail = (response.text or "").strip()[:400]
            # Provider text first: it carries the actionable part, and
            # downstream truncation would otherwise eat it behind the
            # boilerplate status line and MDN link.
            raise httpx.HTTPStatusError(
                f"provider said: {detail} | {exc}",
                request=exc.request,
                response=exc.response,
            ) from exc
        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def is_available(self) -> bool:
        """True only when one of the configured models is actually offered.

        Checking that /models returns 200 is not enough: it proves the
        key is valid and the host is reachable, both of which stay true
        after a provider retires the model we ask for. Groq shut down
        llama-3.3-70b-versatile on 2026-08-16 while /models kept
        answering 200, so every completion failed and silently degraded
        to the mock behind a green health check. Verify membership.
        """
        offered = await self._offered()
        if offered is None:
            # Health is strict where generation is optimistic: if we
            # cannot read the provider, we do not claim it is ready.
            return False
        async with self._resolve_lock:
            chosen = choose_model(self._preferences, offered)
            await self._record(chosen, len(offered))
        return chosen is not None
