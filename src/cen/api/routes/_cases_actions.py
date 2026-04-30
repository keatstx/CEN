"""Action endpoints for cases: approve, provide_input, rewind.

Extracted from ``routes/cases.py`` per CLAUDE.md §4.9. Registered onto
the cases router via ``register_action_routes`` — the action handlers
share ``_save_result_back`` from cases, which is passed in as a
callable so this module doesn't need a circular import.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException

from cen.api.dependencies import (
    get_engines,
    get_event_bus,
    get_session_store,
)
from cen.core.exceptions import (
    ApprovalNotPendingError,
    ModuleNotFoundError,
    SessionNotFoundError,
)
from cen.core.models import (
    ProvideInputRequest,
    SessionStatus,
    WorkflowInput,
    WorkflowResult,
)
from cen.core.session_store import SessionStore
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.events import ApprovalEvent


# The save-back helper lives in sessions.py (it's used by every action
# *and* by the /execute route in workflows.py). We accept it as a
# parameter at registration time to avoid a circular import.
SaveResultBack = Callable[
    [str, list[str], WorkflowResult, SessionStore], Awaitable[None]
]


def register_action_routes(
    router: APIRouter,
    save_result_back: SaveResultBack,
) -> None:
    """Register approve / provide_input / rewind on the supplied router."""

    @router.post("/{case_id}/approve", response_model=WorkflowResult)
    async def approve_case(
        case_id: str,
        engines: dict = Depends(get_engines),
        store: SessionStore = Depends(get_session_store),
        event_bus: AsyncEventBus = Depends(get_event_bus),
    ):
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        if session.status != SessionStatus.AWAITING_APPROVAL:
            raise ApprovalNotPendingError(case_id, session.status.value)

        # Mark the pending node as approved.
        approved_nodes = list(session.approved_nodes)
        pending_node = session.pending_node
        if pending_node:
            approved_nodes.append(pending_node)
        await store.update(
            case_id,
            status=SessionStatus.ACTIVE,
            pending_node=None,
            approved_nodes=approved_nodes,
        )

        if pending_node:
            await event_bus.emit(
                ApprovalEvent(
                    session_id=case_id,
                    module=session.module_name,
                    node_id=pending_node,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

        engine = engines.get(session.module_name)
        if engine is None:
            raise ModuleNotFoundError(session.module_name, list(engines.keys()))

        workflow_input = WorkflowInput(
            module_name=session.module_name, context=session.context
        )
        result = await engine.execute(
            workflow_input,
            approved_nodes=set(approved_nodes),
            session_id=case_id,
        )
        await save_result_back(case_id, session.executed_nodes, result, store)
        return result

    @router.post("/{case_id}/rewind/{node_id}", response_model=WorkflowResult)
    async def rewind_case(
        case_id: str,
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
        target node with the original prompt."""
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
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

        new_context = dict(session.context)
        cache = dict(new_context.get("__node_outputs", {}))
        for nid in nodes_to_purge:
            cache.pop(nid, None)
        new_context["__node_outputs"] = cache

        # Clear input keys the target node owns so the engine pauses
        # again at this node rather than running straight through.
        keys_to_clear: list[str] = []
        if target_node.metadata.input_schema:
            keys_to_clear.extend(f.key for f in target_node.metadata.input_schema)
        if target_node.condition_field:
            keys_to_clear.append(target_node.condition_field)
        keys_to_clear.append(f"{node_id}_result")
        keys_to_clear.append(f"{node_id}_status")
        for k in keys_to_clear:
            new_context.pop(k, None)

        new_approved = [n for n in session.approved_nodes if n != node_id]

        await store.update(
            case_id,
            context=new_context,
            executed_nodes=new_executed,
            approved_nodes=new_approved,
            status=SessionStatus.ACTIVE,
            pending_node=None,
            pending_input_fields=None,
        )

        workflow_input = WorkflowInput(
            module_name=session.module_name, context=new_context
        )
        result = await engine.execute(
            workflow_input,
            approved_nodes=set(new_approved),
            session_id=case_id,
        )
        await save_result_back(case_id, new_executed, result, store)
        return result

    @router.post("/{case_id}/resume_external", response_model=WorkflowResult)
    async def resume_external_case(
        case_id: str,
        engines: dict = Depends(get_engines),
        store: SessionStore = Depends(get_session_store),
    ):
        """Resume a case that's been waiting on a third party (status
        AWAITING_EXTERNAL — set when a HANDOFF node with
        ``pause_on_handoff: true`` paused the workflow).

        Clears the pause state, runs the engine. The cached
        ``__node_outputs`` make this idempotent (Non-Negotiable #3) —
        the HANDOFF node itself replays without re-emitting and the
        workflow advances past it.
        """
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        if session.status != SessionStatus.AWAITING_EXTERNAL:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Case '{case_id}' is not waiting on a third party "
                    f"(current status: {session.status.value})."
                ),
            )

        engine = engines.get(session.module_name)
        if engine is None:
            raise ModuleNotFoundError(session.module_name, list(engines.keys()))

        # Force the cached HANDOFF output to be removed so the engine
        # re-runs that node and proceeds past it. Without this the
        # cache replay short-circuits the resume.
        new_context = dict(session.context)
        cache = dict(new_context.get("__node_outputs", {}))
        if session.pending_node:
            cache.pop(session.pending_node, None)
        new_context["__node_outputs"] = cache

        await store.update(
            case_id,
            status=SessionStatus.ACTIVE,
            pending_node=None,
            context=new_context,
        )

        # Make the HANDOFF act like a normal continue this time: pass
        # a flag through context that the engine can read. Simpler:
        # re-run with the same approved_nodes; the cache miss on the
        # HANDOFF means it executes once more, but pause_on_handoff
        # would re-trigger. To avoid an infinite "resume" loop, we
        # set a per-case context flag that the runtime honors.
        new_context["__resumed_external"] = True
        await store.update(case_id, context=new_context)

        workflow_input = WorkflowInput(
            module_name=session.module_name, context=new_context
        )
        result = await engine.execute(
            workflow_input,
            approved_nodes=set(session.approved_nodes),
            session_id=case_id,
        )
        await save_result_back(case_id, session.executed_nodes, result, store)
        return result

    @router.post("/{case_id}/provide_input", response_model=WorkflowResult)
    async def provide_input(
        case_id: str,
        body: ProvideInputRequest,
        engines: dict = Depends(get_engines),
        store: SessionStore = Depends(get_session_store),
    ):
        """Resume an AWAITING_INPUT case by providing the values the
        engine paused on. The inputs are merged into context and the
        workflow re-executes (idempotent: cached node outputs are not
        re-fired)."""
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        if session.status != SessionStatus.AWAITING_INPUT:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Session '{case_id}' is not awaiting input "
                    f"(current status: {session.status.value})."
                ),
            )

        pending = session.pending_input_fields or []
        missing = [
            f.key for f in pending if f.required and body.inputs.get(f.key) is None
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Missing required inputs: {missing}",
            )

        merged_context = dict(session.context)
        merged_context.update(body.inputs)
        await store.update(
            case_id,
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
            session_id=case_id,
        )
        await save_result_back(case_id, session.executed_nodes, result, store)
        return result
