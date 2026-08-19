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
from cen.core.concierge_prompt import build_context_block, render_prompt
from cen.core.faq_store import FAQStore
from cen.core.concierge_grounding import (
    MIN_FAQ_LEAD_SCORE,
    RetrievedChunk,
    describe_pending_step,
    has_useful_grounding,
    retrieve_input_fields,
    select_lead,
)
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


def _faq_chunk(faq, score: float, from_step: bool = False) -> "RetrievedChunk":
    return RetrievedChunk(
        text=faq.answer,
        score=float(score),
        citation=ConciergeCitation(
            faq_id=faq.id,
            kind="faq",
            question=faq.question,
            score=round(float(score), 3),
            from_step=from_step,
        ),
    )


async def _retrieve_faqs(
    *,
    question: str,
    faq_store: FAQStore,
    module_name: Optional[str],
    project_id: Optional[str],
    owner_id: Optional[str],
    top_k: int = 3,
    boost_tags: Optional[List[str]] = None,
    pin_ids: Optional[List[str]] = None,
) -> List[RetrievedChunk]:
    matches = await faq_store.search(
        question,
        module_name=module_name,
        project_id=project_id,
        owner_id=owner_id,
        top_k=top_k,
        boost_tags=boost_tags,
    )
    boost_set = set(boost_tags or [])
    out: List[RetrievedChunk] = []
    seen: set[str] = set()
    # Pinned FAQs first — always surfaced on this step regardless of
    # lexical/tag match. Scored just above the tag-boost ceiling so they
    # lead the FAQ chunks without displacing the current-step context.
    for faq_id in pin_ids or []:
        faq = await faq_store.get(faq_id)
        if faq is not None and faq.id not in seen:
            seen.add(faq.id)
            out.append(_faq_chunk(faq, 0.9, from_step=True))
    for faq, score in matches:
        if faq.id in seen:
            continue
        seen.add(faq.id)
        # step-scoped when the FAQ shares a tag with the current step.
        shares_tag = bool(boost_set and set(faq.tags) & boost_set)
        out.append(_faq_chunk(faq, score, from_step=shares_tag))
    return out


def _retrieve_workflow_context(
    *,
    case: Optional[Session],
    aop: Optional[AOPDefinition],
    current_node_id: Optional[str],
) -> List[RetrievedChunk]:
    """Surface the current step (and its description) as a retrieval
    chunk so the synthesizer always knows where the navigator is.

    Workflow chunks score at 0.95 so they reliably land in the fused
    context block even when an FAQ matches strongly — the LLM needs to
    know the case state to ground its answer.
    """
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
                    # High score — always include. The LLM needs case
                    # state to answer "what's next" / "what should I do".
                    score=0.95,
                    # Context, not an answer: 0.95 buys inclusion in the
                    # context block, it does not mean this is what the
                    # user asked about.
                    lead_eligible=False,
                    citation=ConciergeCitation(
                        kind="workflow",
                        question=f"Current step — {label}",
                        score=0.95,
                        node_id=pending_id,
                    ),
                )
            )
    if case.executed_nodes:
        completed = ", ".join(case.executed_nodes[-5:])
        chunks.append(
            RetrievedChunk(
                text=f"Steps already done in this case: {completed}.",
                score=0.85,
                lead_eligible=False,
                citation=ConciergeCitation(
                    kind="workflow",
                    question="Recently completed steps",
                    score=0.85,
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


async def _synthesize_with_llm(
    *,
    llm,
    question: str,
    chunks: List[RetrievedChunk],
    history: List[ChatMessage],
    case: Optional[Session],
    aop: Optional[AOPDefinition],
) -> Optional[str]:
    """LLM-grounded conversational reply.

    Builds the prompt from the case state + retrieved chunks + chat
    history, calls the configured LLM. Returns None when the LLM
    isn't configured or the call fails — caller falls back to the
    rule-based path.

    Per CLAUDE.md non-negotiable #5, the deployment_mode + BAA gate
    enforces that real PHI never reaches a non-BAA'd provider. That
    enforcement happens at app startup (``_enforce_deployment_mode``);
    this function trusts the configured backend.
    """
    if llm is None:
        return None
    # Skip the LLM path when the backend is mock — the canned response
    # is meant as a "no LLM" placeholder and would override the
    # rule-based grounding with unhelpful filler text. Real backends
    # (gguf, api) flow through.
    backend = getattr(llm, "backend_name", "")
    if "mock" in backend.lower():
        return None
    chunks_text = [c.text for c in chunks]
    context_block = build_context_block(
        case=case, aop=aop, chunks_text=chunks_text, history=history
    )
    prompt = render_prompt(context_block=context_block, question=question)
    try:
        # generate_checked reports when the stack degraded to the mock
        # (provider outage, retired model id). Canned mock filler must
        # not be returned as a grounded answer — treat it as a miss so
        # the caller uses the rule-based stitcher, which is at least
        # built from the retrieved chunks. Backends without the method
        # (plain Protocol impls, test doubles) keep the old path.
        checked = getattr(llm, "generate_checked", None)
        if checked is not None:
            result = await checked(prompt, max_tokens=320)
            if result.degraded:
                return None
            return result.text.strip()
        return (await llm.generate(prompt, max_tokens=320)).strip()
    except Exception:  # noqa: BLE001
        # LLM failure is recoverable — caller falls back to the
        # rule-based path. Don't crash the user's reply.
        return None


def _synthesize_rule_based(
    *,
    question: str,
    chunks: List[RetrievedChunk],
    history: List[ChatMessage],
    case: Optional[Session],
    aop: Optional[AOPDefinition],
) -> str:
    """Rule-based fallback when no LLM is configured.

    Stitches case context + the top FAQ paragraph + a follow-up offer
    so the navigator sees something useful even with the mock backend.
    Not chatty — but at least grounded.
    """
    if not chunks:
        return _NO_MATCH_REPLY

    user_turn_count = sum(1 for m in history if m.role == "user")
    intro = "" if user_turn_count <= 1 else (
        "Sure — " if user_turn_count == 2 else "Got it. "
    )

    # If we have case state, lead with where the navigator is. This
    # makes the rule-based answer feel less like a search result.
    case_prefix = ""
    if case and case.pending_node and aop:
        node = next((n for n in aop.nodes if n.id == case.pending_node), None)
        if node and node.metadata.label:
            case_prefix = (
                f"You're on \"{node.metadata.label}\" right now. "
            )

    # Lead: the highest-scoring chunk, whatever kind it is. Leading
    # with the top FAQ regardless of score is what answered "what does
    # 'how many people in household' mean" with a paragraph about
    # environmental exposure records — a 0.24 FAQ beat the 0.95
    # current-step chunk purely because it was an FAQ.
    lead_chunk = select_lead(chunks)
    if lead_chunk is None:
        return _NO_MATCH_REPLY
    lead = _first_paragraph(lead_chunk.text)

    # Only advertise *other* FAQs that actually cleared the floor —
    # "I also found 2 related answers" pointing at noise is worse than
    # saying nothing.
    related = [
        c
        for c in chunks
        if c.citation.kind == "faq"
        and c is not lead_chunk
        and c.score >= MIN_FAQ_LEAD_SCORE
    ]
    follow_up = ""
    if related:
        plural = "answer" if len(related) == 1 else "answers"
        follow_up = f" I also found {len(related)} related {plural}."

    return f"{intro}{case_prefix}{lead}{follow_up}".strip()


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
    llm: Optional[object] = None,
    scrubber: Optional[object] = None,
    available_modules: Optional[List[str]] = None,
    # Polymorphic subject (Phase 6). When kind != "case" the case
    # parameter will be None; we ground in the alternate subject's
    # chunks instead.
    subject_kind: str = "case",
    subject_module_name: Optional[str] = None,
    subject_aop: Optional[AOPDefinition] = None,
    subject_sop: Optional[object] = None,  # SOPRecord — typed loose to avoid cycle
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

    # 3) Retrieve from each source. FAQ retrieval is module-scoped
    # whenever a module is known (case or module subject); SOP/queue
    # subjects fall through to global FAQs.
    faq_module = module_name or (case.module_name if case else None) or subject_module_name
    # Resolve the current step so its tags boost matching FAQs and its
    # faq_pin ids are always surfaced (3b, step-scoped FAQ).
    step_tags: Optional[List[str]] = None
    pin_ids: Optional[List[str]] = None
    if aop is not None:
        active_id = current_node_id or (case.pending_node if case else None)
        if active_id:
            step_node = next((n for n in aop.nodes if n.id == active_id), None)
            if step_node is not None:
                step_tags = step_node.metadata.tags
                pin_ids = step_node.metadata.faq_pin
    faq_chunks = await _retrieve_faqs(
        question=question,
        faq_store=faq_store,
        module_name=faq_module,
        project_id=project_id or (case.project_id if case else None),
        owner_id=owner_id,
        boost_tags=step_tags,
        pin_ids=pin_ids,
    )
    workflow_chunks = _retrieve_workflow_context(
        case=case, aop=aop, current_node_id=current_node_id
    )

    # Subject-specific context — Phase 6 polymorphic concierge.
    subject_chunks: List[RetrievedChunk] = []
    if subject_kind == "module" and subject_aop is not None:
        from cen.core.concierge_context import retrieve_module_chunks
        subject_chunks = [
            RetrievedChunk(text=c.text, score=c.score, citation=c.citation)
            for c in retrieve_module_chunks(
                aop=subject_aop, module_name=subject_module_name
            )
        ]
    elif subject_kind == "sop" and subject_sop is not None:
        from cen.core.concierge_context import retrieve_sop_chunks
        subject_chunks = [
            RetrievedChunk(text=c.text, score=c.score, citation=c.citation)
            for c in retrieve_sop_chunks(sop=subject_sop)
        ]

    # The pending step's own input fields. A navigator asking what a
    # field means is answered by the description authored for that
    # field, not by the FAQ library — which knows nothing about it.
    field_chunks = retrieve_input_fields(case=case, question=question)

    fused = _fuse(
        field_chunks, faq_chunks, workflow_chunks + subject_chunks, top_k=6
    )

    # 4) Suggestions: extract structured values from the chat history
    # given the case's pending input fields. Independent of whether
    # we found FAQ matches — the user may have stated values mid-chat
    # that the workflow is about to ask for.
    suggestions = await _extract_suggestions(
        case=case, history=history, llm=llm, scrubber=scrubber
    )

    # 5) Synthesize. Prefer the LLM-grounded path; fall back to the
    # rule-based stitcher when no LLM is configured (or fails).
    #
    # `not fused` was never a real check for "can this be answered":
    # the FAQ store's floor is 0.05, so stopword overlap alone ("what
    # does ... mean") always returned something, and it got asserted as
    # an answer. Require grounding that clears the relevance floor.
    if not has_useful_grounding(fused):
        from cen.core.proactive import derive_actions  # local: avoids cycle

        no_match_actions = derive_actions(
            question=question,
            case=case,
            available_modules=available_modules or [],
        )
        # Say what the step needs even when the library has nothing —
        # "I don't know" alone leaves the navigator stuck.
        step_recap = describe_pending_step(case)
        no_match_answer = _NO_MATCH_REPLY
        if step_recap:
            no_match_answer = f"{_NO_MATCH_REPLY} {step_recap}"
        response = ConciergeResponse(
            answer=no_match_answer,
            mode="no_match",
            suggested_inputs=suggestions,
            actions=no_match_actions,
        )
        await _persist_assistant(chat_store, case, response, owner_id)
        return response

    citations = [c.citation for c in fused]
    answer = await _synthesize_with_llm(
        llm=llm,
        question=question,
        chunks=fused,
        history=history,
        case=case,
        aop=aop,
    )
    if answer:
        mode = "llm_synthesis"
    else:
        answer = _synthesize_rule_based(
            question=question,
            chunks=fused,
            history=history,
            case=case,
            aop=aop,
        )
        mode = "synthesis"

    from cen.core.proactive import derive_actions  # local import: avoids cycle

    actions = derive_actions(
        question=question,
        case=case,
        available_modules=available_modules or [],
    )
    response = ConciergeResponse(
        answer=answer,
        mode=mode,
        citations=citations,
        suggested_inputs=suggestions,
        actions=actions,
    )
    await _persist_assistant(chat_store, case, response, owner_id)
    return response


async def _extract_suggestions(
    *,
    case: Optional[Session],
    history: List[ChatMessage],
    llm: Optional[object] = None,
    scrubber: Optional[object] = None,
) -> List[SuggestedInput]:
    """Run the suggestion extractor against the chat history, scoped
    to the case's currently-pending input fields. Returns [] when the
    case isn't paused for input — the navigator is mid-step and not
    yet looking at a form.

    Uses the LLM extractor when a real backend is available (it fills
    free-text fields regex can't, e.g. patient name) and falls back to
    the deterministic RegexExtractor for mock/no-LLM (keeps tests
    deterministic and never sends chat to a canned backend)."""
    if not case or not case.pending_input_fields:
        return []
    schema: List[InputField] = case.pending_input_fields
    backend = getattr(llm, "backend_name", "") if llm else ""
    if llm is not None and "mock" not in backend.lower():
        from cen.core.suggestions_llm import LLMExtractor

        return await LLMExtractor(llm=llm, scrubber=scrubber).extract(
            history=history, input_schema=schema
        )
    return RegexExtractor().extract(history=history, input_schema=schema)


def opener_for_case(
    *,
    case: Optional[Session],
    aop: Optional[AOPDefinition],
) -> str:
    """Generate a proactive opening message based on case state.

    Rule-based, no LLM call — runs synchronously when the user opens
    the panel. Designed to land warm, oriented, and offer the next
    helpful action so the navigator isn't staring at "ask me anything"
    cold.
    """
    if case is None:
        return (
            "Hi — I'm your CEN concierge. Pick a case from the dashboard "
            "and I'll help you walk through it."
        )

    pending_label = ""
    if case.pending_node and aop:
        node = next((n for n in aop.nodes if n.id == case.pending_node), None)
        if node is not None:
            pending_label = node.metadata.label or case.pending_node

    if case.status == "COMPLETED":
        return (
            f"This case is wrapped up. Anything you want me to recap "
            f"from how it went?"
        )
    if case.status == "FAILED":
        return (
            "This case stopped on an error. Want me to walk through what "
            "happened or help you decide whether to rewind?"
        )
    if case.status == "AWAITING_EXTERNAL":
        return (
            f"You've sent this one to a specialist. When the response "
            f"comes back, click Resume — until then, anything you want "
            f"to prep?"
        )
    if case.status == "AWAITING_APPROVAL" and pending_label:
        return (
            f"You're at \"{pending_label}\" — ready to review. Want me "
            f"to summarize what's been collected so you can sign off?"
        )
    if case.status == "AWAITING_INPUT" and pending_label:
        return (
            f"You're on \"{pending_label}\". Tell me what you've heard "
            f"from the patient and I'll help fill in the form."
        )
    if pending_label:
        return f"You're on \"{pending_label}\". What can I help with?"
    return f"Working on {case.module_name}. What can I help with?"


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
