"""Grounding primitives for the concierge: what counts as a source,
which source leads an answer, and when there is no real answer at all.

Extracted from ``concierge.py`` (619 lines, over the CLAUDE.md §4.9
bar) rather than appended to it.

Motivating failure — a navigator on "Household Data Collection" asked
what the field "How many people live in the household?" meant, and got
back a paragraph about requesting environmental exposure records. Three
things went wrong at once:

1. The text that answered the question — the field's own description,
   "Count everyone who lives there, including children and dependents" —
   was never retrieved. Only the *node's* label and description were.
2. The stitcher always led with the top FAQ even when a much
   higher-scoring workflow chunk existed (0.95 step context lost to a
   0.24 FAQ), because the lead was picked by kind, not by score.
3. Nothing enforced a relevance floor, so a 0.24 cosine built entirely
   out of "what/does/mean" overlap was presented as an answer.

This module fixes all three deterministically — no LLM required, so it
keeps working during a provider outage, which is exactly when the
rule-based path is carrying every reply.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

# Deliberate reuse of the FAQ store's tokenizer/scorer so field matching
# and FAQ matching stay on the same scale — a field chunk scored by a
# different metric could not be ranked against an FAQ chunk.
from cen.core.faq_store import _cosine, _tokenize, _vec
from cen.core.models import ConciergeCitation, InputField, Session


@dataclass
class RetrievedChunk:
    """One grounding chunk produced by a retriever.

    The synthesis layer treats `text` as the body to surface and
    `citation` as the source-of-truth pointer the UI renders.
    """

    text: str
    score: float
    citation: ConciergeCitation
    # Whether this chunk may *lead* an answer, as opposed to merely
    # riding along as context. Case-state chunks carry a fixed high
    # score meaning "always include so the model knows where we are" —
    # that is an inclusion priority, not a relevance measure, and
    # ranking by it would answer "what is charity care?" with "Current
    # step: Collect household income."
    lead_eligible: bool = True


# ── Tuning ───────────────────────────────────────────────────────────
#
# Calibrated against observed cosines on the seeded library: genuine
# matches for "what is charity care?" scored 0.41 / 0.39 / 0.37, while
# the stopword-only garbage that produced the environmental-records
# answer scored 0.24 / 0.23 / 0.21. 0.30 sits in that gap. It is a
# heuristic on a TF-IDF cosine, not a probability — re-measure before
# moving it, and prefer widening the stopword list to raising this.
MIN_FAQ_LEAD_SCORE = 0.30

# Field chunks outrank FAQs when the question is clearly *about* a
# field: the field description is authored for this exact step, so it
# beats any general FAQ. Ranked below the 0.95 current-step chunk so
# case state still leads "what's next"-shaped questions.
FIELD_STRONG_SCORE = 0.93
FIELD_WEAK_SCORE = 0.40

# Share of the question's content words that must appear in the field
# for it to be considered "about" that field.
FIELD_MIN_OVERLAP = 0.5


def _field_text(field: InputField) -> str:
    label = field.label or field.key
    if field.description:
        return (
            f'The field "{label}" on this step means: {field.description}'
        )
    return f'This step is asking for "{label}".'


def retrieve_input_fields(
    *,
    case: Optional[Session],
    question: str,
) -> List[RetrievedChunk]:
    """The pending step's own input fields, as grounding chunks.

    Previously the single biggest blind spot: a navigator asking what a
    field means was answered from the FAQ library, which knows nothing
    about that field, while the authored description sat unused in
    ``pending_input_fields``.

    Only fields the question actually overlaps are returned — surfacing
    all of them would swamp the context block on a step with eight
    inputs.
    """
    if case is None:
        return []
    fields: Sequence[InputField] = case.pending_input_fields or []
    if not fields:
        return []

    q_tokens = _tokenize(question)
    if not q_tokens:
        return []
    q_set = set(q_tokens)
    q_vec = _vec(q_tokens)

    out: List[RetrievedChunk] = []
    for field in fields:
        label = field.label or field.key
        haystack = f"{label} {field.description or ''} {field.key}"
        f_tokens = _tokenize(haystack)
        if not f_tokens:
            continue
        overlap = len(q_set & set(f_tokens)) / len(q_set)
        if overlap <= 0:
            continue
        strong = overlap >= FIELD_MIN_OVERLAP
        # Cosine breaks ties between two fields the question touches.
        tie_break = _cosine(q_vec, _vec(f_tokens)) / 100.0
        out.append(
            RetrievedChunk(
                text=_field_text(field),
                score=(FIELD_STRONG_SCORE if strong else FIELD_WEAK_SCORE)
                + tie_break,
                citation=ConciergeCitation(
                    kind="input_field",
                    question=f"This step — {label}",
                    score=round(overlap, 3),
                ),
            )
        )
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def select_lead(chunks: Sequence[RetrievedChunk]) -> Optional[RetrievedChunk]:
    """The chunk an answer should be built from: the highest-scoring one.

    The old rule — "lead with the top FAQ if any FAQ was retrieved" —
    ignored the ranking the retrievers had just produced, so a 0.24 FAQ
    beat the 0.95 current-step chunk. Respect the scores instead.

    An FAQ that fails the relevance floor is not allowed to lead; it may
    still ride along as a citation, but it will not be asserted as the
    answer.
    """
    if not chunks:
        return None
    eligible = [
        c
        for c in chunks
        if c.lead_eligible
        and (c.citation.kind != "faq" or c.score >= MIN_FAQ_LEAD_SCORE)
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda c: c.score)


def has_useful_grounding(chunks: Sequence[RetrievedChunk]) -> bool:
    """True when at least one chunk is worth building an answer from.

    Retrieval almost always returns *something* — the FAQ store's floor
    is 0.05 — so "the fused list is non-empty" was never a real check
    for whether the question could be answered.
    """
    return select_lead(chunks) is not None


def describe_pending_step(case: Optional[Session]) -> Optional[str]:
    """Plain-language recap of what the current step is asking for.

    Used to make a no-match reply useful instead of a dead end: even
    when nothing in the library matches, the navigator can still be
    told what this step needs from them.
    """
    if case is None:
        return None
    fields: Sequence[InputField] = case.pending_input_fields or []
    if not fields:
        return None
    labels = [f.label or f.key for f in fields if (f.label or f.key)]
    if not labels:
        return None
    if len(labels) == 1:
        return f"Right now this step is asking for: {labels[0]}."
    listed = ", ".join(labels[:-1]) + f", and {labels[-1]}"
    return f"Right now this step is asking for: {listed}."
