"""LanguageModel Protocol — structural typing for LLM backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LanguageModel(Protocol):
    """Any class with these two methods satisfies the protocol."""

    async def generate(self, prompt: str, max_tokens: int = 128) -> str: ...

    async def is_available(self) -> bool: ...

    @property
    def backend_name(self) -> str: ...
