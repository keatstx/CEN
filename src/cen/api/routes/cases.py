"""Case CRUD endpoints + the shared ``_save_result_back`` helper.

Per CLAUDE.md §7, "Case" is the canonical name for one execution of a
workflow; "Session" survives in the data model (SessionStore, Session
model, SessionStatus enum) and in the ``/sessions`` URL alias for
backward compatibility. New routing layers use ``case`` consistently.

Audit endpoints live in ``_cases_audit.py``, case-summary/export
endpoints in ``_cases_exports.py``, and approve/provide_input/rewind
in ``_cases_actions.py``. All three register on the same router via
helper functions called at the bottom of this file (CLAUDE.md §4.9
file-size discipline).
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from cen.api.dependencies import (
    get_current_user,
    get_engines,
    get_project_store,
    get_session_store,
)
from cen.api.routes._cases_actions import register_action_routes
from cen.api.routes._cases_audit import register_audit_routes
from cen.api.routes._cases_exports import register_export_routes
from cen.api.routes._cases_queue import register_queue_routes
from cen.core.exceptions import ModuleNotFoundError, SessionNotFoundError
from cen.core.models import (
    Session,
    SessionCreate,
    SessionStatus,
    SessionUpdate,
    User,
    WorkflowResult,
)
from cen.core.project_store import ProjectStore
from cen.core.session_store import SessionStore

# Router has no prefix — app.py mounts it twice, once at /cases (the
# canonical name, per CLAUDE.md §7) and once at /sessions (legacy
# alias kept for backward compatibility). Both paths share the same
# handlers and the same store.
router = APIRouter(tags=["cases"])

# IMPORTANT: register routes with literal paths (e.g. /queue) BEFORE
# any dynamic-param routes (e.g. /{case_id}). FastAPI matches in
# registration order — without this, GET /cases/queue gets caught by
# /cases/{case_id} with case_id="queue" and returns 404.
register_queue_routes(router)


@router.post("", response_model=Session, status_code=201)
async def create_case(
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
        due_at=body.due_at,
    )


@router.get("", response_model=list[Session])
async def list_cases(
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


@router.get("/{case_id}", response_model=Session)
async def get_case_record(
    case_id: str,
    store: SessionStore = Depends(get_session_store),
):
    session = await store.get(case_id)
    if session is None:
        raise SessionNotFoundError(case_id)
    return session


@router.patch("/{case_id}", response_model=Session)
async def update_case(
    case_id: str,
    body: SessionUpdate,
    store: SessionStore = Depends(get_session_store),
):
    updates = body.model_dump(exclude_none=True)
    session = await store.update(case_id, **updates)
    if session is None:
        raise SessionNotFoundError(case_id)
    return session


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: str,
    store: SessionStore = Depends(get_session_store),
):
    deleted = await store.delete(case_id)
    if not deleted:
        raise SessionNotFoundError(case_id)


async def _save_result_back(
    case_id: str,
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
        # The engine sets pending_node on the result for both
        # pending_approval and pending_input outcomes. Fall back to
        # the last-executed node only if the engine didn't surface a
        # pending_node (defensive — shouldn't happen post-2026-04).
        pending = result.pending_node or (
            result.executed_nodes[-1] if result.executed_nodes else None
        )
        await store.update(
            case_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.AWAITING_APPROVAL,
            pending_node=pending,
            pending_input_fields=None,
        )
    elif result.final_outcome.startswith("pending_input:"):
        await store.update(
            case_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.AWAITING_INPUT,
            pending_node=result.pending_node,
            pending_input_fields=result.pending_input_fields,
        )
    elif result.final_outcome.startswith("awaiting_external:"):
        # HANDOFF node with `pause_on_handoff: true` — case is paused
        # waiting on a third-party response. Resolved via the
        # /resume_external endpoint when the response arrives.
        await store.update(
            case_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.AWAITING_EXTERNAL,
            pending_node=result.pending_node,
            pending_input_fields=None,
        )
    else:
        # handoff:* OR plain "completed" — terminal node reached.
        await store.update(
            case_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=SessionStatus.COMPLETED,
            pending_node=None,
            pending_input_fields=None,
        )


# Register extracted endpoint groups onto the same router so the
# mount path stays unchanged. Per CLAUDE.md §4.9 file-size discipline.
register_audit_routes(router)
register_export_routes(router)
register_action_routes(router, _save_result_back)
# register_queue_routes is called at the top of the file (must come
# before /{case_id} routes — see the comment near `router = ...`).
