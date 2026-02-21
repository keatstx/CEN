"""Workflow execution and AOP management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cen.api.dependencies import get_engines, get_llm
from cen.core.engine import AsyncWorkflowEngine
from cen.core.exceptions import CycleDetectedError, ModuleNotFoundError
from cen.core.models import AOPDefinition, WorkflowInput, WorkflowResult

router = APIRouter()


@router.post("/execute", response_model=WorkflowResult)
async def execute_workflow(
    payload: WorkflowInput,
    engines: dict = Depends(get_engines),
):
    engine = engines.get(payload.module_name)
    if engine is None:
        raise ModuleNotFoundError(payload.module_name, list(engines.keys()))
    return await engine.execute(payload)


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
