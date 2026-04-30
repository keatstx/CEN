"""Concierge service — multi-source RAG + conversational synthesis.

Pipeline per request:

    user question
       │
       ├─► hard guardrail (medical/legal/financial)  ─► fixed refusal
       │
       ▼
    retrieve from three sources, weighted-fuse:
       • FAQ store      (existing TF-IDF)
       • workflow node  (current step + executed history)
       • case context   (input keys/values already collected)
       │
       ▼
    synthesis layer
       • mock / no LLM:  rule-based conversational reply with citations
       • LLM (later):    grounded-prompt synthesis
       │
       ▼
    response { answer, mode, citations } persisted to chat_messages

The retriever and synthesizer are intentionally split so the LLM swap
is one file, not a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from cen.core.chat_store import ChatMessageStore
from cen.core.faq_store import FAQStore
from cen.core.models import (
    AOPDefinition,
    ChatMessage,
    ConciergeCitation,
    ConciergeResponse,
    InputField,
    Session,
    SuggestedInput,
)
from cen.core.suggestions import RegexExtractor


# ── Guardrails (deterministic, fire even when no LLM) ────────────────


_OUT_OF_SCOPE_KEYWORDS = {
    "diagnose",
    "diagnosis",
    "prescribe",
    "prescription",
    "lawsuit",
    "sue ",
    "attorney",
    "settlement",
    "should i pay",
    "should i sign",
    "is this legal",
    "is this fraud",
    "what dose",
    "what medication",
}

_OUT_OF_SCOPE_REPLY = (
    "I'm going to stop here — that question really does need a professional. "
    "I'm a workflow assistant, so I can walk you through steps and pull from the "
    "FAQs your team has uploaded, but I can't give personalized medical, legal, "
    "or financial advice. Your navigator, doctor, attorney, or financial counselor "
    "is the right next stop for that one."
)

_NO_MATCH_REPLY = (
    "I couldn't find anything in your project's FAQ library that lines up with "
    "that question. Try rephrasing it, or ask your navigator. If this comes up "
    "often, your team can add it to the FAQ library so I'll have an answer next "
    "time."
)


def _is_out_of_scope(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _OUT_OF_SCOPE_KEYWORDS)


# ── Retrieval ────────────────────────────────────────────────────────


@dataclass
class RetrievedChunk:
    """One grounding chunk produced by a retriever.

    The synthesis layer treats `text` as the body to surface and
    `citation` as the source-of-truth pointer the UI renders.
    """

    text: str
    score: float
    citation: ConciergeCitation


async def _retrieve_faqs(
    *,
    question: str,
    faq_store: FAQStore,
    module_name: Optional[str],
    project_id: Optional[str],
    owner_id: Optional[str],
    top_k: int = 3,
) -> List[RetrievedChunk]:
    matches = await faq_store.search(
        question,
        module_name=module_name,
        project_id=project_id,
        owner_id=owner_id,
        top_k=top_k,
    )
    out: List[RetrievedChunk] = []
    for faq, score in matches:
        out.append(
            RetrievedChunk(
                text=faq.answer,
                score=float(score),
                citation=ConciergeCitation(
                    faq_id=faq.id,
                    kind="faq",
                    question=faq.question,
                    score=round(float(score), 3),
                ),
            )
        )
    return out


def _retrieve_workflow_context(
    *,
    case: Optional[Session],
    aop: Optional[AOPDefinition],
    current_node_id: Optional[str],
) -> List[RetrievedChunk]:
    """Surface the current step (and its description) as a retrieval
    chunk so the synthesizer can answer "what's next" without a
    matching FAQ."""
    if not case or not aop:
        return []
    chunks: List[RetrievedChunk] = []
    pending_id = current_node_id or case.pending_node
    if pending_id:
        node = next((n for n in aop.nodes if n.id == pending_id), None)
        if node is not None:
            label = node.metadata.label or pending_id
            description = node.metadata.description or ""
            text = f"Current step: {label}.\n{description}".strip()
            chunks.append(
                RetrievedChunk(
                    text=text,
                    score=0.5,  # mid-tier so a strong FAQ match wins
                    citation=ConciergeCitation(
                        kind="workflow",
                        question=f"Current step — {label}",
                        score=0.5,
                        node_id=pending_id,
                    ),
                )
            )
    if case.executed_nodes:
        completed = ", ".join(case.executed_nodes[-5:])
        chunks.append(
            RetrievedChunk(
                text=f"Steps already done in this case: {completed}.",
                score=0.3,
                citation=ConciergeCitation(
                    kind="workflow",
                    question="Recently completed steps",
                    score=0.3,
                ),
            )
        )
    return chunks


def _fuse(*chunk_lists: List[RetrievedChunk], top_k: int = 5) -> List[RetrievedChunk]:
    """Combine retrievers' outputs into one ranked list, deduped."""
    fused: List[RetrievedChunk] = []
    seen_keys: set[tuple[str, str]] = set()
    for chunks in chunk_lists:
        for c in chunks:
            key = (c.citation.kind, c.citation.faq_id or c.citation.node_id or c.citation.question)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            fused.append(c)
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused[:top_k]


# ── Synthesis ────────────────────────────────────────────────────────


def _conversational_intro(history: List[ChatMessage]) -> str:
    """Pick a short opener based on how the conversation is going.

    Rule-based for the mock/gguf path. The LLM path replaces this with
    a real generation — but the rule-based fallback keeps the assistant
    sounding human even with no model attached.
    """
    user_turn_count = sum(1 for m in history if m.role == "user")
    if user_turn_count <= 1:
        return ""  # first turn — straight to the answer
    if user_turn_count == 2:
        return "Sure — "
    return "Got it. "


def _synthesize_answer(
    *,
    question: str,
    chunks: List[RetrievedChunk],
    history: List[ChatMessage],
) -> str:
    """Rule-based conversational reply built from the top chunk.

    The shape is: short conversational intro + the FAQ short answer
    (or the first paragraph of a workflow chunk) + an offer to expand.
    Designed to feel like a person, not an FAQ paste.
    """
    if not chunks:
        return _NO_MATCH_REPLY
    top = chunks[0]
    intro = _conversational_intro(history)

    # FAQ chunks have a short answer on the first line; the body is
    # multi-paragraph. Take the first non-empty paragraph as the lead.
    lead = _first_paragraph(top.text)
    rest_count = max(0, len([p for p in top.text.split("\n\n") if p.strip()]) - 1)

    follow_up = ""
    if rest_count > 0 and top.citation.kind == "faq":
        follow_up = " Want me to pull up the full answer or sources?"

    other_count = len(chunks) - 1
    if other_count > 0:
        plural = "answer" if other_count == 1 else "answers"
        follow_up += f" I also found {other_count} related {plural} you can ask about."

    return f"{intro}{lead}{follow_up}".strip()


def _first_paragraph(text: str) -> str:
    for para in text.split("\n\n"):
        s = para.strip()
        if s:
            return s
    return text.strip()


# ── Public entry point ──────────────────────────────────────────────


async def answer_question(
    question: str,
    *,
    faq_store: FAQStore,
    chat_store: Optional[ChatMessageStore] = None,
    case: Optional[Session] = None,
    aop: Optional[AOPDefinition] = None,
    current_node_id: Optional[str] = None,
    module_name: Optional[str] = None,
    project_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> ConciergeResponse:
    """Answer a user question.

    The question is assumed PII-scrubbed by the caller. Persistence to
    chat_messages happens here when chat_store + case are both provided
    (so the route layer doesn't have to remember to log both turns).
    """

    history: List[ChatMessage] = []
    if chat_store is not None and case is not None:
        history = await chat_store.list_recent_for_case(
            case.id, owner_id=owner_id, limit=6
        )

    # 1) Persist the user turn first so the audit trail is immediate.
    if chat_store is not None and case is not None:
        await chat_store.append(
            case_id=case.id,
            role="user",
            content=question,
            owner_id=owner_id,
        )
        history = history + [
            ChatMessage(
                id="",
                case_id=case.id,
                role="user",
                content=question,
                owner_id=owner_id,
            )
        ]

    # 2) Hard guardrail.
    if _is_out_of_scope(question):
        response = ConciergeResponse(answer=_OUT_OF_SCOPE_REPLY, mode="guardrail")
        await _persist_assistant(chat_store, case, response, owner_id)
        return response

    # 3) Retrieve from each source.
    faq_chunks = await _retrieve_faqs(
        question=question,
        faq_store=faq_store,
        module_name=module_name or (case.module_name if case else None),
        project_id=project_id or (case.project_id if case else None),
        owner_id=owner_id,
    )
    workflow_chunks = _retrieve_workflow_context(
        case=case, aop=aop, current_node_id=current_node_id
    )
    fused = _fuse(faq_chunks, workflow_chunks, top_k=5)

    # 4) Suggestions: extract structured values from the chat history
    # given the case's pending input fields. Independent of whether
    # we found FAQ matches — the user may have stated values mid-chat
    # that the workflow is about to ask for.
    suggestions = _extract_suggestions(case=case, history=history)

    # 5) Synthesize.
    if not fused:
        response = ConciergeResponse(
            answer=_NO_MATCH_REPLY, mode="no_match", suggested_inputs=suggestions
        )
        await _persist_assistant(chat_store, case, response, owner_id)
        return response

    answer = _synthesize_answer(question=question, chunks=fused, history=history)
    citations = [c.citation for c in fused]
    response = ConciergeResponse(
        answer=answer,
        mode="synthesis",
        citations=citations,
        suggested_inputs=suggestions,
    )
    await _persist_assistant(chat_store, case, response, owner_id)
    return response


def _extract_suggestions(
    *,
    case: Optional[Session],
    history: List[ChatMessage],
) -> List[SuggestedInput]:
    """Run the suggestion extractor against the chat history, scoped
    to the case's currently-pending input fields. Returns [] when the
    case isn't paused for input — the navigator is mid-step and not
    yet looking at a form."""
    if not case or not case.pending_input_fields:
        return []
    schema: List[InputField] = case.pending_input_fields
    return RegexExtractor().extract(history=history, input_schema=schema)


async def _persist_assistant(
    chat_store: Optional[ChatMessageStore],
    case: Optional[Session],
    response: ConciergeResponse,
    owner_id: Optional[str],
) -> None:
    if chat_store is None or case is None:
        return
    try:
        await chat_store.append(
            case_id=case.id,
            role="assistant",
            content=response.answer,
            citations=response.citations,
            mode=response.mode,
            owner_id=owner_id,
        )
    except Exception:  # noqa: BLE001
        # Persistence errors must not block the user's reply. Per
        # CLAUDE.md §4.1 — never let an audit/event-emit failure
        # block the user mutation.
        pass
