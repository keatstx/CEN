"""Session CRUD endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from cen.api.dependencies import get_engines, get_session_store
from cen.core.exceptions import ModuleNotFoundError, SessionNotFoundError
from cen.core.models import Session, SessionCreate, SessionUpdate
from cen.core.session_store import SessionStore

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=Session, status_code=201)
async def create_session(
    body: SessionCreate,
    engines: dict = Depends(get_engines),
    store: SessionStore = Depends(get_session_store),
):
    if body.module_name not in engines:
        raise ModuleNotFoundError(body.module_name, list(engines.keys()))
    return await store.create(body.module_name, body.context or {})


@router.get("", response_model=list[Session])
async def list_sessions(
    module_name: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    store: SessionStore = Depends(get_session_store),
) -> List[Session]:
    return await store.list_sessions(module_name=module_name, limit=limit)


@router.get("/{session_id}", response_model=Session)
async def get_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


@router.patch("/{session_id}", response_model=Session)
async def update_session(
    session_id: str,
    body: SessionUpdate,
    store: SessionStore = Depends(get_session_store),
):
    updates = body.model_dump(exclude_none=True)
    session = await store.update(session_id, **updates)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    deleted = await store.delete(session_id)
    if not deleted:
        raise SessionNotFoundError(session_id)
