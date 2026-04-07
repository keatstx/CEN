"""Concierge service — retrieves FAQs and (optionally) formats with an LLM.

v1 ships with two response modes:
- "lookup": returns the top-matching FAQ verbatim. Deterministic, no
  LLM call. Safe even when CEN_DEPLOYMENT_MODE=production. This is
  the default.
- "format": will format the retrieved FAQ chunks with Gemini Flash for
  a more natural answer. Wired through but currently a no-op fallback
  to lookup when no Gemini backend is configured. The full Gemini
  swap lands in a follow-up commit.

Per CLAUDE.md non-negotiable #1, the user's question is PII-scrubbed
before retrieval (the scrubber runs in the route layer before this
function is called).

Per CLAUDE.md §5 concierge guardrails, every response begins with a
disclaimer when no FAQ matches and refuses to provide medical/legal
advice. The guardrail is applied here, not in the LLM prompt, so it
fires even in pure lookup mode.
"""

from __future__ import annotations

from typing import Optional

from cen.core.faq_store import FAQStore
from cen.core.models import ConciergeCitation, ConciergeResponse


_NO_MATCH_FALLBACK = (
    "I couldn't find a matching answer in the FAQ library for this project. "
    "Try rephrasing your question, or ask your navigator. "
    "I can only answer using the FAQs your team has uploaded — I can't give "
    "personalized medical, legal, or financial advice."
)

_OUT_OF_SCOPE_KEYWORDS = {
    "diagnose",
    "diagnosis",
    "prescribe",
    "prescription",
    "lawsuit",
    "sue",
    "attorney",
    "settle",
    "settlement",
    "should i pay",
    "should i sign",
    "is this legal",
    "is this fraud",
}


def _is_out_of_scope(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _OUT_OF_SCOPE_KEYWORDS)


_OUT_OF_SCOPE_RESPONSE = (
    "That question needs a professional. I'm a workflow assistant — "
    "I can explain steps and help you find information from your project's "
    "FAQs, but I can't give personalized medical, legal, or financial advice. "
    "Please ask your navigator, doctor, attorney, or financial counselor."
)


async def answer_question(
    question: str,
    *,
    faq_store: FAQStore,
    module_name: Optional[str] = None,
    project_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    mode: str = "lookup",
) -> ConciergeResponse:
    """Answer a user question using the FAQ store + the requested mode.

    The question is assumed to already be PII-scrubbed by the caller.
    """
    if _is_out_of_scope(question):
        return ConciergeResponse(
            answer=_OUT_OF_SCOPE_RESPONSE,
            mode="guardrail",
            citations=[],
        )

    matches = await faq_store.search(
        question,
        module_name=module_name,
        project_id=project_id,
        owner_id=owner_id,
        top_k=3,
    )

    if not matches:
        return ConciergeResponse(
            answer=_NO_MATCH_FALLBACK,
            mode="lookup",
            citations=[],
        )

    citations = [
        ConciergeCitation(
            faq_id=faq.id,
            question=faq.question,
            score=round(score, 3),
        )
        for faq, score in matches
    ]

    # Lookup mode: return the top match verbatim. Format mode is wired
    # through but currently falls back to lookup when no LLM formatter
    # is available — see TODO below.
    top_faq, _top_score = matches[0]

    if mode == "format":
        # TODO: when CEN_LLM_BACKEND is configured for Gemini (or any
        # OpenAI-compatible chat endpoint), call it here with a strict
        # prompt: "Answer the user's question USING ONLY the provided
        # FAQ chunks. Cite which FAQs you used. If they don't cover the
        # question, say so." For v1 we silently fall back to lookup so
        # the endpoint always returns a deterministic, grounded answer.
        pass

    return ConciergeResponse(
        answer=top_faq.answer,
        mode="lookup",
        citations=citations,
    )
