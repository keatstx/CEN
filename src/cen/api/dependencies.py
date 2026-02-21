"""FastAPI Depends() providers — wired at app creation time."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from cen.config import Settings

if TYPE_CHECKING:
    from cen.core.audit_store import AuditStore
    from cen.core.engine import AsyncWorkflowEngine
    from cen.core.session_store import SessionStore
    from cen.llm.factory import FallbackLanguageModel
    from cen.telemetry.bus import AsyncEventBus

# These are populated by create_app() at startup.
_settings: Settings | None = None
_engines: dict[str, AsyncWorkflowEngine] = {}
_llm: FallbackLanguageModel | None = None
_session_store: SessionStore | None = None
_audit_store: AuditStore | None = None
_event_bus: AsyncEventBus | None = None


def init_dependencies(
    settings: Settings,
    engines: dict[str, AsyncWorkflowEngine],
    llm: FallbackLanguageModel,
    session_store: SessionStore | None = None,
    audit_store: AuditStore | None = None,
    event_bus: AsyncEventBus | None = None,
) -> None:
    global _settings, _engines, _llm, _session_store, _audit_store, _event_bus
    _settings = settings
    _engines = engines
    _llm = llm
    _session_store = session_store
    _audit_store = audit_store
    _event_bus = event_bus


def get_settings() -> Settings:
    assert _settings is not None
    return _settings


def get_engines() -> dict[str, AsyncWorkflowEngine]:
    return _engines


def get_llm() -> FallbackLanguageModel:
    assert _llm is not None
    return _llm


def get_session_store() -> SessionStore:
    assert _session_store is not None
    return _session_store


def get_audit_store() -> AuditStore:
    assert _audit_store is not None
    return _audit_store


def get_event_bus() -> AsyncEventBus:
    assert _event_bus is not None
    return _event_bus
