"""Concierge + FAQ admin endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from cen.api.dependencies import (
    get_chat_store,
    get_current_user,
    get_engines,
    get_faq_store,
    get_llm,
    get_session_store,
)
from cen.core.chat_store import ChatMessageStore
from cen.core.concierge import answer_question, opener_for_case
from cen.core.exceptions import SessionNotFoundError
from cen.core.faq_import import import_faqs
from cen.core.faq_store import FAQStore
from cen.core.models import (
    ChatMessage,
    ConciergeQuery,
    ConciergeResponse,
    FAQ,
    FAQCreate,
    SuggestedInput,
    User,
)
from cen.core.session_store import SessionStore
from cen.core.suggestions import RegexExtractor
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


class ImportFAQResponse(BaseModel):
    imported: int
    source_filename: str


@router.post("/faqs/import", response_model=ImportFAQResponse, status_code=201)
async def import_faq_library(
    file: UploadFile = File(...),
    store: FAQStore = Depends(get_faq_store),
    user: User = Depends(get_current_user),
) -> ImportFAQResponse:
    """Bulk-import an FAQ library from a Markdown file.

    Use-case headings (e.g. "# Use Case 1: Charity Care") map to module
    names so retrieval auto-scopes to the right workflow. Entries from
    use cases without a CEN module land as global FAQs.
    """
    body = await file.read(5 * 1024 * 1024)  # 5 MB cap; FAQ files are small
    name = (file.filename or "faq_library.md").lower()
    if not name.endswith((".md", ".markdown", ".txt")):
        raise HTTPException(
            status_code=415,
            detail="FAQ imports must be a Markdown (.md) file.",
        )
    text = body.decode("utf-8", errors="replace")
    count = await import_faqs(
        text=text,
        faq_store=store,
        source_filename=file.filename or "faq_library.md",
        owner_id=user.id,
    )
    return ImportFAQResponse(imported=count, source_filename=file.filename or "")


# ── Concierge query + history ──────────────────────────────────────


@router.post("/concierge/ask", response_model=ConciergeResponse)
async def ask_concierge(
    body: ConciergeQuery,
    faq_store: FAQStore = Depends(get_faq_store),
    chat_store: ChatMessageStore = Depends(get_chat_store),
    case_store: SessionStore = Depends(get_session_store),
    engines: dict = Depends(get_engines),
    llm=Depends(get_llm),
    user: User = Depends(get_current_user),
) -> ConciergeResponse:
    """Answer a question using the FAQ store, the case's workflow
    state, and chat history. The user's question is PII-scrubbed
    before retrieval per CLAUDE.md non-negotiable #1.

    When the LLM backend is configured (anything other than mock),
    the synthesis path uses it for warm, grounded replies. The
    backend choice is enforced by the deployment_mode + BAA gate at
    app startup (Non-Negotiable #5), so this layer trusts whatever's
    wired.
    """
    scrubbed_question = _scrubber.scrub(body.question)

    case = None
    aop = None
    if body.case_id:
        case = await case_store.get(body.case_id)
        if case is None:
            raise SessionNotFoundError(body.case_id)
        if case.owner_id is not None and case.owner_id != user.id:
            raise SessionNotFoundError(body.case_id)
        engine = engines.get(case.module_name)
        aop = engine._aop if engine is not None else None  # noqa: SLF001

    return await answer_question(
        scrubbed_question,
        faq_store=faq_store,
        chat_store=chat_store if case is not None else None,
        case=case,
        aop=aop,
        current_node_id=body.current_node_id,
        owner_id=user.id,
        llm=llm,
    )


@router.get("/concierge/history/{case_id}", response_model=list[ChatMessage])
async def get_chat_history(
    case_id: str,
    chat_store: ChatMessageStore = Depends(get_chat_store),
    case_store: SessionStore = Depends(get_session_store),
    user: User = Depends(get_current_user),
) -> List[ChatMessage]:
    """Load the persisted chat thread for a case, oldest first."""
    case = await case_store.get(case_id)
    if case is None:
        raise SessionNotFoundError(case_id)
    if case.owner_id is not None and case.owner_id != user.id:
        raise SessionNotFoundError(case_id)
    return await chat_store.list_for_case(case_id, owner_id=user.id)


class OpenerResponse(BaseModel):
    message: str


@router.get(
    "/concierge/opener/{case_id}", response_model=OpenerResponse
)
async def get_concierge_opener(
    case_id: str,
    case_store: SessionStore = Depends(get_session_store),
    engines: dict = Depends(get_engines),
    user: User = Depends(get_current_user),
) -> OpenerResponse:
    """Proactive opening message for the concierge panel — landed
    warm and oriented when the user opens a case, before they've
    asked anything. Rule-based; no LLM call."""
    case = await case_store.get(case_id)
    if case is None:
        raise SessionNotFoundError(case_id)
    if case.owner_id is not None and case.owner_id != user.id:
        raise SessionNotFoundError(case_id)
    engine = engines.get(case.module_name)
    aop = engine._aop if engine is not None else None  # noqa: SLF001
    return OpenerResponse(message=opener_for_case(case=case, aop=aop))


@router.get(
    "/concierge/suggestions/{case_id}", response_model=list[SuggestedInput]
)
async def get_suggestions(
    case_id: str,
    chat_store: ChatMessageStore = Depends(get_chat_store),
    case_store: SessionStore = Depends(get_session_store),
    user: User = Depends(get_current_user),
) -> List[SuggestedInput]:
    """Re-run suggestion extraction over the case's persisted chat
    history against the currently-pending input fields. Returns [] when
    the case isn't paused on a form-input step."""
    case = await case_store.get(case_id)
    if case is None:
        raise SessionNotFoundError(case_id)
    if case.owner_id is not None and case.owner_id != user.id:
        raise SessionNotFoundError(case_id)
    if not case.pending_input_fields:
        return []
    history = await chat_store.list_for_case(case_id, owner_id=user.id)
    return RegexExtractor().extract(
        history=history, input_schema=case.pending_input_fields
    )
