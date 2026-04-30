"""Prompt assembly for the LLM-backed concierge.

Loads ``src/cen/prompts/concierge.md`` once, builds a context block
from the case state + retrieved chunks + chat history, and renders
the final prompt for the LLM. Extracted so concierge.py stays under
the §4.9 size limit.

The prompt template uses two placeholders:
- ``{context_block}`` — case state + retrieved chunks + chat history
- ``{question}`` — the user's current question (PII-scrubbed)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from cen.core.models import AOPDefinition, ChatMessage, Session


_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "concierge.md"
)


@lru_cache(maxsize=1)
def _load_template() -> str:
    """Load the prompt template once. lru_cache so repeat callers
    don't re-read the file. The template is small enough that holding
    it in memory is fine."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Defensive: ship a minimal fallback if the template file is
        # missing (e.g., partial deploy). Prevents 500s.
        return (
            "You are the CEN AI Concierge — a workflow co-pilot for "
            "community navigators. Speak warmly, briefly, at an "
            "8th-grade reading level. Ground every answer in the "
            "context below.\n\n{context_block}\n\nQuestion: {question}\n\n"
            "Reply:"
        )


def build_context_block(
    *,
    case: Optional[Session],
    aop: Optional[AOPDefinition],
    chunks_text: List[str],
    history: List[ChatMessage],
    history_limit: int = 6,
) -> str:
    """Compose the {context_block} the prompt expects.

    Sections (each present only when data is available):
    - "Current case" — module, step label, what's been collected
    - "FAQs and references" — numbered chunk list
    - "Recent chat" — last N turns, oldest first

    Returns an empty string when nothing's available — the LLM still
    gets the question, just without grounding.
    """
    sections: list[str] = []

    case_block = _case_block(case, aop)
    if case_block:
        sections.append(case_block)

    if chunks_text:
        chunk_lines = [f"  [{i + 1}] {c}" for i, c in enumerate(chunks_text)]
        sections.append(
            "## FAQs and references\n" + "\n\n".join(chunk_lines)
        )

    history_block = _history_block(history, history_limit)
    if history_block:
        sections.append(history_block)

    return "\n\n".join(sections)


def render_prompt(*, context_block: str, question: str) -> str:
    template = _load_template()
    return template.format(context_block=context_block, question=question)


# ── Helpers ──────────────────────────────────────────────────────────


def _case_block(
    case: Optional[Session], aop: Optional[AOPDefinition]
) -> str:
    if not case:
        return ""
    lines = [f"## Current case", f"Workflow: {case.module_name}"]
    if case.name and case.name != case.module_name:
        lines.append(f"Case name: {case.name}")
    pending_label = _pending_step_label(case, aop)
    if pending_label:
        lines.append(f"Current step: {pending_label}")
    if case.executed_nodes:
        lines.append(
            f"Steps already done: {', '.join(case.executed_nodes[-5:])}"
        )
    collected = _summarize_context(case.context)
    if collected:
        lines.append(f"Collected so far: {collected}")
    return "\n".join(lines)


def _pending_step_label(
    case: Session, aop: Optional[AOPDefinition]
) -> str:
    if not case.pending_node:
        return ""
    if not aop:
        return case.pending_node
    node = next((n for n in aop.nodes if n.id == case.pending_node), None)
    if node is None:
        return case.pending_node
    return node.metadata.label or case.pending_node


def _summarize_context(context: dict) -> str:
    """Return a one-line summary of the user-collected fields.

    Filters out engine-internal keys (``__node_outputs``, *_status,
    *_result, *_llm_response) so the LLM sees only navigator-supplied
    data. Trims long values to 80 chars apiece.
    """
    pairs: list[str] = []
    for key, value in context.items():
        if key.startswith("__") or key.endswith(("_status", "_result", "_llm_response")):
            continue
        rendered = _render_value(value)
        if rendered:
            pairs.append(f"{key} = {rendered}")
    if not pairs:
        return ""
    # Cap to 8 fields — long context wastes tokens.
    return "; ".join(pairs[:8])


def _render_value(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).strip()
    return s[:80] + ("…" if len(s) > 80 else "")


def _history_block(history: List[ChatMessage], limit: int) -> str:
    """Render the last N turns. Skip the system role; tag the rest as
    Navigator / Concierge so the LLM follows the right turn-taking
    pattern."""
    rendered: list[str] = []
    for msg in history[-limit:]:
        if msg.role == "user":
            rendered.append(f"Navigator: {msg.content}")
        elif msg.role == "assistant":
            rendered.append(f"Concierge: {msg.content}")
    if not rendered:
        return ""
    return "## Recent chat\n" + "\n".join(rendered)
