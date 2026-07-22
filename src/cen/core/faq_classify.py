"""Classify FAQ entries by workflow function so step-scoped FAQ
retrieval fires (3b).

A FAQ tagged ``function:eligibility_check`` gets a relevance boost on
steps tagged the same — genuine step-level scoping, finer than the
existing module_name (workflow-level) filter. We deliberately tag
*function only*, not domain: domain is already covered by module_name
scoping, and a domain tag on every FAQ would make the "From this step"
badge fire indiscriminately.

Two classifiers behind one interface:
- ``heuristic_function`` — deterministic keyword match, no LLM. Runs
  anywhere, reproducible; the default.
- ``llm_function`` — asks the configured LLM to pick one function from
  the vocabulary. Higher quality on educational/indirect phrasing;
  requires a real backend (Groq in prod).

Both feed a one-time CLI pass (``python -m cen.core.faq_classify``) that
writes a reviewable overlay (``seed/faq_function_tags.json``, keyed by
question text). The FAQ importer reads that overlay and attaches the
tags at seed time — so classification is a durable artifact, not a
runtime cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from cen.core.tags import vocabulary
from cen.sop.extractor import _PHASE_FUNCTION_MAP

_OVERLAY_PATH = (
    Path(__file__).resolve().parent.parent / "seed" / "faq_function_tags.json"
)


def _valid_functions() -> set[str]:
    return set(vocabulary().get("function", []))


def heuristic_function(question: str, answer: str) -> Optional[str]:
    """Keyword match against the shared function vocabulary. Matches on
    the question first (focused), then the answer. Returns a namespaced
    tag or None when nothing clearly applies (educational FAQs often
    map to no workflow function — that's fine)."""
    for text in (question.lower(), answer[:240].lower()):
        for keyword, value in _PHASE_FUNCTION_MAP:
            if keyword in text:
                return f"function:{value}"
    return None


def _llm_prompt(question: str, functions: List[str]) -> str:
    options = ", ".join(functions)
    return (
        "You label a FAQ by which workflow step it most helps a patient "
        "navigator with. Choose EXACTLY ONE label from this list, or the "
        f"word none if no single step fits:\n{options}\n\n"
        f'FAQ question: "{question}"\n\n'
        "Reply with only the label, nothing else."
    )


async def llm_function(question: str, answer: str, llm) -> Optional[str]:
    """Ask the LLM to pick one function. Validates the reply against the
    vocabulary; returns None on 'none', an unknown value, or any error
    (caller keeps the heuristic result in that case)."""
    valid = _valid_functions()
    try:
        raw = await llm.generate(_llm_prompt(question, sorted(valid)), max_tokens=16)
    except Exception:
        return None
    token = raw.strip().split()[0].strip().lower() if raw.strip() else ""
    token = token.replace("function:", "").strip(".,:;\"'")
    return f"function:{token}" if token in valid else None


def load_overlay() -> Dict[str, List[str]]:
    """Read the question -> tags overlay produced by the classify pass.
    Missing/corrupt overlay yields an empty dict (importer falls back to
    the inline heuristic)."""
    try:
        return json.loads(_OVERLAY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_overlay(mapping: Dict[str, List[str]]) -> None:
    _OVERLAY_PATH.write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


async def _run_cli(mode: str) -> int:
    """Regenerate the overlay from the bundled seed. mode: heuristic|llm."""
    from cen.core.faq_import import parse_faq_markdown

    seed = _OVERLAY_PATH.parent / "faq_library.md"
    parsed = parse_faq_markdown(seed.read_text(encoding="utf-8"))

    llm = None
    if mode == "llm":
        from cen.config import Settings
        from cen.llm.factory import create_language_model

        llm = create_language_model(Settings())

    mapping: Dict[str, List[str]] = {}
    tagged = 0
    for entry in parsed:
        fn = heuristic_function(entry.question, entry.answer)
        if mode == "llm":
            llm_fn = await llm_function(entry.question, entry.answer, llm)
            fn = llm_fn or fn  # LLM wins; heuristic is the fallback
        if fn:
            mapping[entry.question] = [fn]
            tagged += 1
    _write_overlay(mapping)
    print(f"[{mode}] classified {tagged}/{len(parsed)} FAQs -> {_OVERLAY_PATH.name}")
    return tagged


if __name__ == "__main__":
    import argparse
    import asyncio

    ap = argparse.ArgumentParser(description="Classify seed FAQs by workflow function.")
    ap.add_argument("--mode", choices=["heuristic", "llm"], default="heuristic")
    args = ap.parse_args()
    asyncio.run(_run_cli(args.mode))
