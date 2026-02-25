"""Module definition routes — expose AOP graph data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from cen.api.dependencies import get_engines
from cen.core.models import AOPDefinition

router = APIRouter()


@router.get("/modules/{name}", response_model=AOPDefinition)
async def get_module(
    name: str,
    engines: dict = Depends(get_engines),
):
    engine = engines.get(name)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"Module '{name}' not found")
    return engine._aop
