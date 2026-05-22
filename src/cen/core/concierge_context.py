"""Per-subject retrievers for the polymorphic concierge.

The concierge's center-of-attention isn't always a case. When the user
is on the Workflow Map tab, they're inspecting a module. On SOP Studio,
a draft AOP and its validation issues. On Dashboard, the bucketed
queue. Each subject needs different grounding chunks so the assistant's
answer matches what's on screen.

This module lives outside `core/concierge.py` (509+ lines) per
CLAUDE.md §4.9 file-size discipline.
"""

from __future__ import annotations

from typing import List, Optional

from cen.core.models import (
    AOPDefinition,
    ConciergeCitation,
    ConciergeContext,
    Session,
    SOPRecord,
)


class ContextChunk:
    """Mirrors the internal _Chunk shape used by core/concierge.py's
    fuser. Kept lightweight — just the bits the synthesizer needs."""

    __slots__ = ("text", "score", "citation")

    def __init__(self, text: str, score: float, citation: ConciergeCitation):
        self.text = text
        self.score = score
        self.citation = citation


# ── Module subject (Workflow Map tab) ──────────────────────────────


def retrieve_module_chunks(
    *,
    aop: Optional[AOPDefinition],
    module_name: Optional[str],
) -> List[ContextChunk]:
    """Surface the module's description + node/edge counts + node-type
    breakdown so the concierge can answer 'what does this workflow do?'
    without hallucinating.
    """
    if aop is None:
        return []
    by_type: dict[str, int] = {}
    for n in aop.nodes:
        by_type[n.type] = by_type.get(n.type, 0) + 1
    type_summary = ", ".join(f"{c} {t.lower()}" for t, c in sorted(by_type.items()))
    text = (
        f"Workflow: {module_name or aop.module_name} (v{aop.version}). "
        f"{aop.description}\n"
        f"Structure: {len(aop.nodes)} steps total ({type_summary}), "
        f"{len(aop.edges)} transitions."
    )
    return [
        ContextChunk(
            text=text,
            score=0.95,
            citation=ConciergeCitation(
                kind="workflow",
                question=f"About this workflow: {module_name or aop.module_name}",
                score=0.95,
            ),
        )
    ]


# ── SOP subject (SOP Studio tab) ───────────────────────────────────


def retrieve_sop_chunks(*, sop: Optional[SOPRecord]) -> List[ContextChunk]:
    """Ground in the active SOP — its draft AOP, validation issues, and
    a snippet of the canonical markdown. Limits to the top issues so we
    don't blow the prompt window on a 50-issue SOP.
    """
    if sop is None:
        return []
    chunks: List[ContextChunk] = []

    # Lead chunk: SOP identity + status + counts.
    issues = sop.validation_issues or []
    err = sum(1 for i in issues if i.severity == "error")
    warn = sum(1 for i in issues if i.severity == "warning")
    draft_summary = ""
    if sop.draft_module:
        draft_summary = (
            f" Draft has {len(sop.draft_module.nodes)} steps and "
            f"{len(sop.draft_module.edges)} transitions."
        )
    lead_text = (
        f"SOP: {sop.filename} (status: {sop.status}).{draft_summary} "
        f"Validation: {err} error(s), {warn} warning(s)."
    )
    chunks.append(
        ContextChunk(
            text=lead_text,
            score=0.95,
            citation=ConciergeCitation(
                kind="sop",
                question=f"About this SOP: {sop.filename}",
                score=0.95,
                sop_id=sop.id,
            ),
        )
    )

    # Top errors first — those are what the navigator most likely
    # needs to discuss. Cap to 5 so the context block stays sane.
    sorted_issues = sorted(
        issues,
        key=lambda i: (0 if i.severity == "error" else 1, i.message[:50]),
    )
    for issue in sorted_issues[:5]:
        node_ref = f" (step {issue.node_id})" if issue.node_id else ""
        chunks.append(
            ContextChunk(
                text=f"{issue.severity.upper()}{node_ref}: {issue.message}",
                score=0.85,
                citation=ConciergeCitation(
                    kind="sop",
                    question=f"Issue on {sop.filename}",
                    score=0.85,
                    sop_id=sop.id,
                    node_id=issue.node_id,
                ),
            )
        )

    # Canonical markdown excerpt — first 500 chars when present.
    if sop.canonical_md:
        excerpt = sop.canonical_md[:500].strip()
        if excerpt:
            chunks.append(
                ContextChunk(
                    text=f"From the SOP source:\n{excerpt}",
                    score=0.80,
                    citation=ConciergeCitation(
                        kind="sop",
                        question=f"Source: {sop.filename}",
                        score=0.80,
                        sop_id=sop.id,
                    ),
                )
            )

    return chunks


# ── Queue subject (Dashboard tab) ──────────────────────────────────


def retrieve_queue_chunks(
    *,
    needs_attention_count: int,
    waiting_external_count: int,
    in_progress_count: int,
    failed_count: int,
) -> List[ContextChunk]:
    """A one-line snapshot of the navigator's queue so the concierge
    can say 'you have 3 cases needing attention' instead of guessing.
    """
    pieces: List[str] = []
    if needs_attention_count:
        pieces.append(f"{needs_attention_count} case(s) need your attention")
    if waiting_external_count:
        pieces.append(f"{waiting_external_count} waiting on an external response")
    if in_progress_count:
        pieces.append(f"{in_progress_count} in progress")
    if failed_count:
        pieces.append(f"{failed_count} stopped on an error")
    if not pieces:
        text = "Your queue is empty right now."
    else:
        text = "Right now: " + "; ".join(pieces) + "."
    return [
        ContextChunk(
            text=text,
            score=0.90,
            citation=ConciergeCitation(
                kind="case_context",
                question="Your case queue",
                score=0.90,
            ),
        )
    ]


# ── Context dispatcher ─────────────────────────────────────────────


def normalize_context(
    *,
    query_context: Optional[ConciergeContext],
    legacy_case_id: Optional[str],
    legacy_node_id: Optional[str],
) -> ConciergeContext:
    """Build a ConciergeContext from the request, honoring the legacy
    `case_id`/`current_node_id` fields when the new `context` block
    isn't present. Defaults to kind='none' when nothing is supplied."""
    if query_context is not None:
        return query_context
    if legacy_case_id:
        return ConciergeContext(
            kind="case",
            case_id=legacy_case_id,
            current_node_id=legacy_node_id,
        )
    return ConciergeContext(kind="none")
