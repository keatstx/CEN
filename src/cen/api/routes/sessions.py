"""Session CRUD endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from cen.api.dependencies import (
    get_artifact_store,
    get_audit_store,
    get_current_user,
    get_engines,
    get_event_bus,
    get_project_store,
    get_session_store,
    get_storage_backend,
)
from cen.core.artifact_store import ArtifactStore
from cen.core.audit_export import export_csv, export_json
from cen.core.audit_store import AuditStore
from cen.core.case_export import (
    build_case_packet_zip,
    case_summary_dict,
    render_case_summary_html,
)
from cen.core.exceptions import ApprovalNotPendingError, ModuleNotFoundError, SessionNotFoundError
from cen.core.models import AuditEntry, AuditVerification, ProvideInputRequest, Session, SessionCreate, SessionStatus, SessionUpdate, User, WorkflowInput, WorkflowResult
from cen.core.project_store import ProjectStore
from cen.core.session_store import SessionStore
from cen.storage.base import StorageBackend
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


@router.get("/{session_id}/summary")
async def case_summary(
    session_id: str,
    format: str = Query(default="html", pattern="^(html|json)$"),
    store: SessionStore = Depends(get_session_store),
    artifact_store: ArtifactStore = Depends(get_artifact_store),
    user: User = Depends(get_current_user),
) -> Response:
    """Render the case as a printable summary. Format can be html
    (default — opens in a browser tab, save/print to PDF) or json
    (machine-readable structured data)."""
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if session.owner_id is not None and session.owner_id != user.id:
        raise SessionNotFoundError(session_id)
    artifacts = await artifact_store.list_for_case(session_id, owner_id=user.id)

    if format == "json":
        payload = case_summary_dict(session, artifacts)
        return Response(
            content=json.dumps(payload, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="case_{session_id}_summary.json"'
                ),
            },
        )

    html_content = render_case_summary_html(session, artifacts)
    return Response(
        content=html_content,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/{session_id}/export")
async def case_export(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
    artifact_store: ArtifactStore = Depends(get_artifact_store),
    storage: StorageBackend = Depends(get_storage_backend),
    user: User = Depends(get_current_user),
) -> Response:
    """Bundle the case as a single ZIP packet containing summary.html,
    summary.json, and a documents/ folder with every uploaded file.
    One-click hand-off for the navigator to email, archive, or share.
    """
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if session.owner_id is not None and session.owner_id != user.id:
        raise SessionNotFoundError(session_id)

    artifacts = await artifact_store.list_for_case(session_id, owner_id=user.id)
    blobs: dict[str, bytes] = {}
    for a in artifacts:
        try:
            blobs[a.id] = await storage.read(a.storage_key)
        except FileNotFoundError:
            # Skip blobs that disappeared on disk; the summary will
            # still list them.
            continue

    zip_bytes = build_case_packet_zip(session, artifacts, blobs)
    # Content-Disposition headers must be ASCII (latin-1). Strip
    # non-ASCII characters from the auto-generated case name (which
    # may contain em dashes, accented chars, etc.) and fall back to
    # the case id if nothing usable remains.
    raw_name = session.name or session_id
    safe_name = "".join(
        c if (c.isascii() and c not in '/\\:*?"<>|') else "_"
        for c in raw_name
    ).strip("_ ") or session_id
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="case_{safe_name}.zip"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{session_id}/rewind/{node_id}", response_model=WorkflowResult)
async def rewind_session(
    session_id: str,
    node_id: str,
    engines: dict = Depends(get_engines),
    store: SessionStore = Depends(get_session_store),
):
    """Rewind a case to a previously-executed step so the navigator
    can edit the answer they provided. Clears the target node and
    every node after it from the executed list, drops their entries
    from the idempotency cache, and clears any input fields the
    target node owns. Re-executes — engine walks the DAG again,
    replays cached entries that still exist, and pauses at the
    target node with the original prompt.

    No-op if the target node is not in the case's executed_nodes.
    """
    session = await store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    if node_id not in session.executed_nodes:
        raise HTTPException(
            status_code=400,
            detail=f"Step '{node_id}' has not been reached yet — nothing to rewind to.",
        )

    engine = engines.get(session.module_name)
    if engine is None:
        raise ModuleNotFoundError(session.module_name, list(engines.keys()))
    target_node = engine.nodes.get(node_id)
    if target_node is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown node '{node_id}' in module."
        )

    idx = session.executed_nodes.index(node_id)
    new_executed = session.executed_nodes[:idx]
    nodes_to_purge = session.executed_nodes[idx:]

    # Drop the cached node outputs for the target and everything
    # downstream so they re-execute fresh.
    new_context = dict(session.context)
    cache = dict(new_context.get("__node_outputs", {}))
    for nid in nodes_to_purge:
        cache.pop(nid, None)
    new_context["__node_outputs"] = cache

    # Clear the input keys the target node owns so the engine pauses
    # again when it hits the target. Without this, the engine sees
    # the existing values in context and runs straight through.
    keys_to_clear: list[str] = []
    if target_node.metadata.input_schema:
        keys_to_clear.extend(f.key for f in target_node.metadata.input_schema)
    if target_node.condition_field:
        keys_to_clear.append(target_node.condition_field)
    # CONDITION result fields cached by the engine
    keys_to_clear.append(f"{node_id}_result")
    keys_to_clear.append(f"{node_id}_status")
    for k in keys_to_clear:
        new_context.pop(k, None)

    # Drop the target from approved_nodes if it was an APPROVAL.
    new_approved = [n for n in session.approved_nodes if n != node_id]

    await store.update(
        session_id,
        context=new_context,
        executed_nodes=new_executed,
        approved_nodes=new_approved,
        status=SessionStatus.ACTIVE,
        pending_node=None,
        pending_input_fields=None,
    )

    # Re-run the workflow. The engine walks topologically, replays
    # any cached entries that survived the purge, and pauses again
    # at the target node (or earlier if other inputs are missing).
    workflow_input = WorkflowInput(
        module_name=session.module_name, context=new_context
    )
    result = await engine.execute(
        workflow_input,
        approved_nodes=set(new_approved),
        session_id=session_id,
    )
    await _save_result_back(session_id, new_executed, result, store)
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
