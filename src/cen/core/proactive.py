"""Per-step proactive prompts for the Concierge.

Lives outside `core/concierge.py` (509+ lines) per CLAUDE.md §4.9
file-size discipline — adding step-level proactive prompt logic to the
core concierge module would push it past the bar. This module composes
the next-question payload the frontend uses to swap the chat header on
every step change.

The endpoint `GET /concierge/next_question/{case_id}` reads from this
module; see `api/routes/concierge.py`.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from cen.core.models import AOPDefinition, Session


class NextQuestion(BaseModel):
    """Payload returned to the frontend per step.

    `field_key` is the AOPNode input field the chat should focus on
    next (or None when the case is not paused on an input form).
    `prompt` is the warm proactive sentence to render as the assistant's
    next turn. `suggested_questions` is the hand-authored chip set from
    the AOP node metadata.
    """

    field_key: Optional[str] = None
    prompt: str
    suggested_questions: List[str] = []


def _find_node(aop: AOPDefinition, node_id: str):
    return next((n for n in aop.nodes if n.id == node_id), None)


def proactive_prompt_for_step(
    *,
    case: Session,
    aop: Optional[AOPDefinition],
) -> NextQuestion:
    """Return the next proactive prompt + step-aware chips for a case.

    Status-aware:
    - AWAITING_INPUT → "Let's get [field.label]. [field.description]"
      for the first unfilled required field, falling back to the first
      field when nothing is marked required.
    - AWAITING_APPROVAL → "Ready for your review on [step label]?"
    - AWAITING_EXTERNAL / COMPLETED / FAILED → defer to the simpler
      per-status copy used by `opener_for_case`.
    """
    questions: List[str] = []
    node = None
    if case.pending_node and aop is not None:
        node = _find_node(aop, case.pending_node)
        if node is not None:
            questions = list(node.metadata.suggested_questions or [])

    label = (node.metadata.label if node else None) or case.pending_node or ""

    if case.status == "AWAITING_INPUT" and case.pending_input_fields:
        first_field = next(
            (f for f in case.pending_input_fields if f.required),
            case.pending_input_fields[0],
        )
        prompt = _input_prompt(label, first_field)
        return NextQuestion(
            field_key=first_field.key,
            prompt=prompt,
            suggested_questions=questions,
        )

    if case.status == "AWAITING_APPROVAL":
        prompt = (
            f"Ready for your review on \"{label}\"? Want me to summarize "
            f"what's been collected so you can sign off?"
            if label
            else "Ready for your review. Want me to summarize what's been collected?"
        )
        return NextQuestion(prompt=prompt, suggested_questions=questions)

    if case.status == "AWAITING_EXTERNAL":
        return NextQuestion(
            prompt=(
                "You've sent this one to a specialist. When the response "
                "comes back, click Resume — until then, anything you want to prep?"
            ),
            suggested_questions=questions,
        )

    if case.status == "COMPLETED":
        return NextQuestion(
            prompt="This case is wrapped up. Want me to recap how it went?",
            suggested_questions=[],
        )

    if case.status == "FAILED":
        return NextQuestion(
            prompt=(
                "This case stopped on an error. Want me to walk through "
                "what happened or help you decide whether to rewind?"
            ),
            suggested_questions=[],
        )

    # ACTIVE or anything else — generic "what can I help with"
    prompt = (
        f"You're on \"{label}\". What can I help with?"
        if label
        else f"Working on {case.module_name}. What can I help with?"
    )
    return NextQuestion(prompt=prompt, suggested_questions=questions)


def _input_prompt(step_label: str, field) -> str:
    """Build the proactive single-field prompt. Uses field.label (NOT
    field.key) per CLAUDE.md §5 forbidden-terms compliance."""
    label = field.label or field.key
    desc = (field.description or "").strip()
    intro = (
        f"You're on \"{step_label}\". Let's start with: {label}."
        if step_label
        else f"Let's start with: {label}."
    )
    if desc:
        return f"{intro} {desc}"
    return intro
