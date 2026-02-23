"""Session CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from cen.api.dependencies import get_audit_store, get_engines, get_event_bus, get_session_store
from cen.core.audit_export import export_csv, export_json
from cen.core.audit_store import AuditStore
from cen.core.exceptions import ApprovalNotPendingError, ModuleNotFoundError, SessionNotFoundError
from cen.core.models import AuditEntry, AuditVerification, Session, SessionCreate, SessionStatus, SessionUpdate, WorkflowInput, WorkflowResult
from cen.core.session_store import SessionStore
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.events import ApprovalEvent

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


@router.get("/{session_id}/audit", response_model=list[AuditEntry])
async def get_audit_trail(
    session_id: str,
    node_type: Optional[str] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    store: SessionStore = Depends(get_session_store),
    audit_store: AuditStore = Depends(get_audit_store),
) -> List[AuditEntry]:
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return await audit_store.query(
        session_id=session_id,
        node_type=node_type,
        outcome=outcome,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )


@router.get("/{session_id}/audit/verify", response_model=AuditVerification)
async def verify_audit_trail(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
    audit_store: AuditStore = Depends(get_audit_store),
) -> AuditVerification:
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    is_valid, last_verified_id, total_records = await audit_store.verify_chain(session_id)
    return AuditVerification(
        is_valid=is_valid,
        last_verified_id=last_verified_id,
        total_records=total_records,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/{session_id}/audit/export")
async def export_audit_trail(
    session_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    node_type: Optional[str] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
    start_time: Optional[str] = Query(default=None),
    end_time: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    store: SessionStore = Depends(get_session_store),
    audit_store: AuditStore = Depends(get_audit_store),
) -> Response:
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    entries = await audit_store.query(
        session_id=session_id,
        node_type=node_type,
        outcome=outcome,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    if format == "csv":
        content = export_csv(entries)
        media_type = "text/csv"
        filename = f"audit_{session_id}.csv"
    else:
        content = export_json(entries)
        media_type = "application/json"
        filename = f"audit_{session_id}.json"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{session_id}/approve", response_model=WorkflowResult)
async def approve_session(
    session_id: str,
    engines: dict = Depends(get_engines),
    store: SessionStore = Depends(get_session_store),
    event_bus: AsyncEventBus = Depends(get_event_bus),
):
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if session.status != SessionStatus.AWAITING_APPROVAL:
        raise ApprovalNotPendingError(session_id, session.status.value)

    # Mark the pending node as approved
    approved_nodes = list(session.approved_nodes)
    pending_node = session.pending_node
    if pending_node:
        approved_nodes.append(pending_node)
    await store.update(
        session_id,
        status=SessionStatus.ACTIVE,
        pending_node=None,
        approved_nodes=approved_nodes,
    )

    # Emit approval event
    if pending_node:
        await event_bus.emit(
            ApprovalEvent(
                session_id=session_id,
                module=session.module_name,
                node_id=pending_node,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    # Re-execute the workflow from the top with approved nodes
    engine = engines.get(session.module_name)
    if engine is None:
        raise ModuleNotFoundError(session.module_name, list(engines.keys()))

    workflow_input = WorkflowInput(module_name=session.module_name, context=session.context)
    result = await engine.execute(workflow_input, approved_nodes=set(approved_nodes), session_id=session_id)

    # Save result back to session (same logic as /execute)
    combined_nodes = list(dict.fromkeys(session.executed_nodes + result.executed_nodes))
    if result.final_outcome.startswith("pending_approval:"):
        pending = result.executed_nodes[-1] if result.executed_nodes else None
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.AWAITING_APPROVAL,
            pending_node=pending,
        )
    elif result.final_outcome.startswith("handoff:"):
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.COMPLETED,
            pending_node=None,
        )
    else:
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.ACTIVE,
            pending_node=None,
        )

    return result
