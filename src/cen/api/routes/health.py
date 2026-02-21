"""Health and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cen.api.dependencies import get_engines, get_llm
from cen.core.models import HealthResponse, ReadyResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    engines: dict = Depends(get_engines),
    llm=Depends(get_llm),
):
    return ReadyResponse(
        status="ok",
        modules_loaded=list(engines.keys()),
        llm_backend=llm.backend_name,
        llm_available=await llm.is_available(),
    )
