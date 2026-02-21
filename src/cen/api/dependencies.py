"""FastAPI Depends() providers — wired at app creation time."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from cen.config import Settings

if TYPE_CHECKING:
    from cen.core.engine import AsyncWorkflowEngine
    from cen.llm.factory import FallbackLanguageModel

# These are populated by create_app() at startup.
_settings: Settings | None = None
_engines: dict[str, AsyncWorkflowEngine] = {}
_llm: FallbackLanguageModel | None = None


def init_dependencies(
    settings: Settings,
    engines: dict[str, AsyncWorkflowEngine],
    llm: FallbackLanguageModel,
) -> None:
    global _settings, _engines, _llm
    _settings = settings
    _engines = engines
    _llm = llm


def get_settings() -> Settings:
    assert _settings is not None
    return _settings


def get_engines() -> dict[str, AsyncWorkflowEngine]:
    return _engines


def get_llm() -> FallbackLanguageModel:
    assert _llm is not None
    return _llm
