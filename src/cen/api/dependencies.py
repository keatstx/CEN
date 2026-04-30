"""FastAPI Depends() providers — wired at app creation time."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Optional

from fastapi import Header, HTTPException, status

from cen.config import Settings
from cen.core.models import User


# v1 stub operator returned when auth is disabled (operator_password = "").
# The fixed id ensures all v1 cases share the same owner_id, which keeps
# the multi-tenant filter path exercised even before real auth lands.
_DEV_STUB_USER = User(id="default-operator", name="Default Operator")

if TYPE_CHECKING:
    import asyncio

    from cen.core.artifact_store import ArtifactStore
    from cen.core.audit_store import AuditStore
    from cen.core.chat_store import ChatMessageStore
    from cen.core.engine import AsyncWorkflowEngine
    from cen.core.faq_store import FAQStore
    from cen.core.project_store import ProjectStore
    from cen.core.session_store import SessionStore
    from cen.llm.factory import FallbackLanguageModel
    from cen.sop.store import SOPStore
    from cen.storage.base import StorageBackend
    from cen.telemetry.bus import AsyncEventBus

# These are populated by create_app() at startup.
_settings: Settings | None = None
_engines: dict[str, AsyncWorkflowEngine] = {}
_llm: FallbackLanguageModel | None = None
_llm_semaphore: "asyncio.Semaphore | None" = None
_session_store: SessionStore | None = None
_project_store: ProjectStore | None = None
_audit_store: AuditStore | None = None
_artifact_store: ArtifactStore | None = None
_faq_store: FAQStore | None = None
_chat_store: ChatMessageStore | None = None
_sop_store: SOPStore | None = None
_storage_backend: StorageBackend | None = None
_event_bus: AsyncEventBus | None = None


def init_dependencies(
    settings: Settings,
    engines: dict[str, AsyncWorkflowEngine],
    llm: FallbackLanguageModel,
    session_store: SessionStore | None = None,
    project_store: ProjectStore | None = None,
    audit_store: AuditStore | None = None,
    artifact_store: ArtifactStore | None = None,
    faq_store: FAQStore | None = None,
    chat_store: "ChatMessageStore | None" = None,
    sop_store: "SOPStore | None" = None,
    storage_backend: StorageBackend | None = None,
    event_bus: AsyncEventBus | None = None,
    llm_semaphore: "asyncio.Semaphore | None" = None,
) -> None:
    global _settings, _engines, _llm, _llm_semaphore, _session_store, _project_store
    global _audit_store, _artifact_store, _faq_store, _chat_store, _sop_store
    global _storage_backend, _event_bus
    _settings = settings
    _engines = engines
    _llm = llm
    _llm_semaphore = llm_semaphore
    _session_store = session_store
    _project_store = project_store
    _audit_store = audit_store
    _artifact_store = artifact_store
    _faq_store = faq_store
    _chat_store = chat_store
    _sop_store = sop_store
    _storage_backend = storage_backend
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


def get_project_store() -> ProjectStore:
    assert _project_store is not None
    return _project_store


def get_artifact_store() -> ArtifactStore:
    assert _artifact_store is not None
    return _artifact_store


def get_faq_store() -> FAQStore:
    assert _faq_store is not None
    return _faq_store


def get_storage_backend() -> StorageBackend:
    assert _storage_backend is not None
    return _storage_backend


def get_audit_store() -> AuditStore:
    assert _audit_store is not None
    return _audit_store


def get_event_bus() -> AsyncEventBus:
    assert _event_bus is not None
    return _event_bus


def get_sop_store() -> "SOPStore":
    assert _sop_store is not None
    return _sop_store


def get_chat_store() -> "ChatMessageStore":
    assert _chat_store is not None
    return _chat_store


def get_llm_semaphore():
    return _llm_semaphore


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> User:
    """Authenticate the request and return the current operator.

    v1 model:
    - If `CEN_OPERATOR_PASSWORD` is empty (the default in dev/test),
      auth is disabled and a stub user is returned. Every request gets
      `owner_id="default-operator"`. This keeps multi-tenant filter
      paths exercised even with no real auth.
    - If `CEN_OPERATOR_PASSWORD` is set, the request must include
      `Authorization: Bearer <password>`. The password is the bearer
      token (single shared password — prototype only). Real JWT and
      per-user accounts come in a future hardening milestone.
    """
    settings = get_settings()
    if not settings.operator_password:
        return _DEV_STUB_USER
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(None, 1)[1].strip()
    if token != settings.operator_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _DEV_STUB_USER
