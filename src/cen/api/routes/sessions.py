"""Session CRUD endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from cen.api.dependencies import (
    get_audit_store,
    get_current_user,
    get_engines,
    get_event_bus,
    get_project_store,
    get_session_store,
)
from cen.core.audit_export import export_csv, export_json
from cen.core.audit_store import AuditStore
from cen.core.exceptions import ApprovalNotPendingError, ModuleNotFoundError, SessionNotFoundError
from cen.core.models import AuditEntry, AuditVerification, ProvideInputRequest, Session, SessionCreate, SessionStatus, SessionUpdate, User, WorkflowInput, WorkflowResult
from cen.core.project_store import ProjectStore
from cen.core.session_store import SessionStore
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.events import ApprovalEvent

# Router has no prefix — app.py mounts it twice, once at /sessions
# (legacy) and once at /cases (the canonical name going forward, per
# CLAUDE.md §7). Both paths share the same handlers and the same store.
router = APIRouter(tags=["sessions"])


@router.post("", response_model=Session, status_code=201)
async def create_session(
    body: SessionCreate,
    engines: dict = Depends(get_engines),
    store: SessionStore = Depends(get_session_store),
    project_store: ProjectStore = Depends(get_project_store),
    user: User = Depends(get_current_user),
):
    if body.module_name not in engines:
        raise ModuleNotFoundError(body.module_name, list(engines.keys()))

    # Pin module version on the case at creation time so future engine
    # updates do not affect in-flight cases.
    engine = engines[body.module_name]
    aop = getattr(engine, "_aop", None)
    module_version = getattr(aop, "version", "1.0") if aop is not None else "1.0"

    # Resolve project_id: explicit if provided, otherwise the owner's
    # default project (auto-created on first use).
    project_id = body.project_id
    if project_id is None:
        default_project = await project_store.get_or_create_default(owner_id=user.id)
        project_id = default_project.id

    return await store.create(
        body.module_name,
        body.context or {},
        module_version=module_version,
        name=body.name,
        owner_id=user.id,
        project_id=project_id,
    )


@router.get("", response_model=list[Session])
async def list_sessions(
    module_name: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    store: SessionStore = Depends(get_session_store),
    user: User = Depends(get_current_user),
) -> List[Session]:
    return await store.list_sessions(
        module_name=module_name,
        project_id=project_id,
        owner_id=user.id,
        limit=limit,
    )


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


async def _save_result_back(
    session_id: str,
    prior_executed: list[str],
    result: WorkflowResult,
    store: SessionStore,
) -> None:
    """Persist a workflow execution result to the session, handling all
    three pause/terminal outcomes: pending_approval, pending_input, or
    terminal (completed/handoff).
    """
    combined_nodes = list(dict.fromkeys(prior_executed + result.executed_nodes))
    if result.final_outcome.startswith("pending_approval:"):
        pending = result.executed_nodes[-1] if result.executed_nodes else None
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.AWAITING_APPROVAL,
            pending_node=pending,
            pending_input_fields=None,
        )
    elif result.final_outcome.startswith("pending_input:"):
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.AWAITING_INPUT,
            pending_node=result.pending_node,
            pending_input_fields=result.pending_input_fields,
        )
    else:
        # handoff:* OR plain "completed" — terminal node reached.
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.COMPLETED,
            pending_node=None,
            pending_input_fields=None,
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

    await _save_result_back(session_id, session.executed_nodes, result, store)
    return result


@router.post("/{session_id}/provide_input", response_model=WorkflowResult)
async def provide_input(
    session_id: str,
    body: ProvideInputRequest,
    engines: dict = Depends(get_engines),
    store: SessionStore = Depends(get_session_store),
):
    """Resume an AWAITING_INPUT case by providing the values the engine
    paused on. The inputs are merged into context and the workflow
    re-executes (idempotent: cached node outputs are not re-fired)."""
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if session.status != SessionStatus.AWAITING_INPUT:
        raise HTTPException(
            status_code=409,
            detail=f"Session '{session_id}' is not awaiting input "
            f"(current status: {session.status.value}).",
        )

    # Validate that all currently-required fields were provided.
    pending = session.pending_input_fields or []
    missing = [
        f.key for f in pending if f.required and body.inputs.get(f.key) is None
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required inputs: {missing}",
        )

    # Merge the provided inputs into context, clear the pending state,
    # and re-execute. The engine's idempotency cache ensures already-run
    # nodes don't re-fire (CLAUDE.md non-negotiable #3).
    merged_context = dict(session.context)
    merged_context.update(body.inputs)
    await store.update(
        session_id,
        status=SessionStatus.ACTIVE,
        pending_node=None,
        pending_input_fields=None,
        context=merged_context,
    )

    engine = engines.get(session.module_name)
    if engine is None:
        raise ModuleNotFoundError(session.module_name, list(engines.keys()))
    workflow_input = WorkflowInput(
        module_name=session.module_name, context=merged_context
    )
    result = await engine.execute(
        workflow_input,
        approved_nodes=set(session.approved_nodes),
        session_id=session_id,
    )

    await _save_result_back(session_id, session.executed_nodes, result, store)
    return result
