"""Concierge + FAQ admin endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from cen.api.dependencies import (
    get_current_user,
    get_faq_store,
    get_session_store,
)
from cen.core.concierge import answer_question
from cen.core.exceptions import SessionNotFoundError
from cen.core.faq_store import FAQStore
from cen.core.models import (
    ConciergeQuery,
    ConciergeResponse,
    FAQ,
    FAQCreate,
    User,
)
from cen.core.session_store import SessionStore
from cen.privacy.pii_scrubber import create_scrubber

# A single shared scrubber for the concierge prompt assembly path. The
# scrubber is configured at app startup based on CEN_PII_BACKEND, but
# the route layer holds its own instance to make the dependency
# explicit per CLAUDE.md non-negotiable #1.
_scrubber = create_scrubber("regex")


router = APIRouter(tags=["concierge"])


# ── FAQ admin ──────────────────────────────────────────────────────


@router.post("/faqs", response_model=FAQ, status_code=201)
async def create_faq(
    body: FAQCreate,
    store: FAQStore = Depends(get_faq_store),
    user: User = Depends(get_current_user),
) -> FAQ:
    return await store.create(
        question=body.question,
        answer=body.answer,
        module_name=body.module_name,
        project_id=body.project_id,
        source_filename=body.source_filename,
        owner_id=user.id,
    )


@router.get("/faqs", response_model=list[FAQ])
async def list_faqs(
    module_name: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    store: FAQStore = Depends(get_faq_store),
    user: User = Depends(get_current_user),
) -> List[FAQ]:
    return await store.list_all(
        module_name=module_name,
        project_id=project_id,
        owner_id=user.id,
    )


@router.delete("/faqs/{faq_id}", status_code=204)
async def delete_faq(
    faq_id: str,
    store: FAQStore = Depends(get_faq_store),
    user: User = Depends(get_current_user),
) -> None:
    existing = await store.get(faq_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="FAQ not found")
    if existing.owner_id is not None and existing.owner_id != user.id:
        raise HTTPException(status_code=404, detail="FAQ not found")
    await store.delete(faq_id)


# ── Concierge query ─────────────────────────────────────────────────


@router.post("/concierge/ask", response_model=ConciergeResponse)
async def ask_concierge(
    body: ConciergeQuery,
    faq_store: FAQStore = Depends(get_faq_store),
    case_store: SessionStore = Depends(get_session_store),
    user: User = Depends(get_current_user),
) -> ConciergeResponse:
    """Answer a question using the FAQ store, scoped to the case's
    module + project. The user's question is PII-scrubbed before
    retrieval per CLAUDE.md non-negotiable #1.
    """
    # Scrub the question. The scrubber is best-effort regex/Presidio;
    # the route layer enforces the boundary.
    scrubbed_question = _scrubber.scrub(body.question)

    module_name: Optional[str] = None
    project_id: Optional[str] = None
    if body.case_id:
        case = await case_store.get(body.case_id)
        if case is None:
            raise SessionNotFoundError(body.case_id)
        if case.owner_id is not None and case.owner_id != user.id:
            raise SessionNotFoundError(body.case_id)
        module_name = case.module_name
        project_id = case.project_id

    return await answer_question(
        scrubbed_question,
        faq_store=faq_store,
        module_name=module_name,
        project_id=project_id,
        owner_id=user.id,
    )
