"""LLM generation route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from cen.api.dependencies import get_llm
from cen.core.models import LLMGenerateRequest, LLMGenerateResponse

router = APIRouter()


@router.post("/tlm/generate", response_model=LLMGenerateResponse)
async def tlm_generate(
    body: LLMGenerateRequest,
    llm=Depends(get_llm),
):
    response = await llm.generate(body.prompt, body.max_tokens)
    return LLMGenerateResponse(response=response, backend=llm.backend_name)
