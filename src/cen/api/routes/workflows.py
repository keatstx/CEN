"""Workflow execution and AOP management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from cen.api.dependencies import get_engines, get_llm, get_session_store
from cen.core.engine import AsyncWorkflowEngine
from cen.core.exceptions import CycleDetectedError, ModuleNotFoundError, SessionNotFoundError
from cen.core.models import AOPDefinition, SessionStatus, WorkflowInput, WorkflowResult
from cen.core.session_store import SessionStore

router = APIRouter()


@router.post("/execute", response_model=WorkflowResult)
async def execute_workflow(
    payload: WorkflowInput,
    engines: dict = Depends(get_engines),
    store: SessionStore = Depends(get_session_store),
    session_id: Optional[str] = Query(default=None),
):
    engine = engines.get(payload.module_name)
    if engine is None:
        raise ModuleNotFoundError(payload.module_name, list(engines.keys()))

    # If session_id provided, load and merge context
    if session_id is not None:
        session = await store.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        # Merge: saved context as base, incoming overrides
        merged = {**session.context, **payload.context}
        payload = WorkflowInput(module_name=payload.module_name, context=merged)

    result = await engine.execute(payload)

    # Persist result back to session
    if session_id is not None:
        combined_nodes = list(dict.fromkeys(session.executed_nodes + result.executed_nodes))
        status = SessionStatus.COMPLETED if result.final_outcome.startswith("handoff:") else SessionStatus.ACTIVE
        await store.update(
            session_id,
            context=result.context,
            executed_nodes=combined_nodes,
            status=status,
        )

    return result


@router.post("/update-aop")
async def update_aop(
    aop: AOPDefinition,
    engines: dict = Depends(get_engines),
    llm=Depends(get_llm),
):
    engine = AsyncWorkflowEngine(llm=llm)
    engine.load_aop(aop)  # raises CycleDetectedError if invalid
    engines[aop.module_name] = engine
    return {
        "status": "ok",
        "module": aop.module_name,
        "nodes": len(aop.nodes),
        "edges": len(aop.edges),
    }
