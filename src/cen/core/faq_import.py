"""Import an FAQ library Markdown file into the FAQ store.

The expected format (matches the CEN FAQ Library v2):

    # Use Case 1: Charity Care
    ### Stage: Awareness

    **Q1: What exactly is charity care…?**
    **A (Short):** …
    **A (Full):** …
    **Sources:**
    - [Title](https://…)

The parser is deterministic — no LLM. It tolerates extra blank lines,
nested formatting (bold/italics in the answer body), and the
horizontal-rule separators (`---`, `***`) that the library uses
between entries.

Use Case names map to existing CEN module names so retrieval can
auto-scope to the right workflow:

    Charity Care        -> charity_care_navigator
    Medical Debt        -> debt_cancellation_engine
    Prior Authorization -> insurance_appeal_assistant
    Workplace Injuries  -> (no module yet — leaves NULL, scoped global)
    Toxic Exposure      -> (no module yet — leaves NULL, scoped global)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

from cen.core.faq_store import FAQStore


# Use-case heading -> module_name. Anything not in this map imports as
# a global FAQ (module_name=NULL).
_USE_CASE_TO_MODULE: dict[str, str] = {
    "charity care": "charity_care_navigator",
    "medical debt": "debt_cancellation_engine",
    "prior authorization": "insurance_appeal_assistant",
    "insurance appeal": "insurance_appeal_assistant",
    "benefits enrollment": "benefits_enrollment_navigator",
    "community resource": "community_resource_router",
}


_USE_CASE_HEADER = re.compile(r"^#\s+Use\s+Case\s+\d+\s*:\s*(?P<name>.+?)\s*$", re.IGNORECASE)
_QUESTION_LINE = re.compile(r"^\*\*Q\d+\s*:\s*(?P<q>.+?)\*\*\s*$")
_SHORT_ANSWER = re.compile(r"^\*\*A\s*\(Short\)\s*:\*\*\s*(?P<a>.*)$", re.IGNORECASE)
_FULL_ANSWER = re.compile(r"^\*\*A\s*\(Full\)\s*:\*\*\s*(?P<a>.*)$", re.IGNORECASE)
_SIMPLE_ANSWER = re.compile(r"^\*\*A\s*:\*\*\s*(?P<a>.*)$", re.IGNORECASE)
_SOURCES_HEADER = re.compile(r"^\*\*Sources?\s*:\*\*\s*$", re.IGNORECASE)


@dataclass
class ParsedFAQ:
    question: str
    answer: str  # full answer + sources, ready to drop into the store
    use_case: str  # raw label from the markdown
    module_name: Optional[str]


def parse_faq_markdown(text: str) -> list[ParsedFAQ]:
    """Walk the markdown line-by-line and emit one ParsedFAQ per Q block."""
    lines = text.splitlines()
    current_use_case = ""
    current_module: Optional[str] = None

    out: list[ParsedFAQ] = []
    i = 0
    while i < len(lines):
        line = lines[i]

        m = _USE_CASE_HEADER.match(line)
        if m:
            current_use_case = m.group("name").strip()
            current_module = _module_for_use_case(current_use_case)
            i += 1
            continue

        q_match = _QUESTION_LINE.match(line)
        if not q_match:
            i += 1
            continue

        question = q_match.group("q").strip()
        i += 1

        short_answer = ""
        full_answer = ""
        sources_lines: list[str] = []

        # Walk until the next question header, use-case header, or EOF.
        while i < len(lines):
            ln = lines[i]
            if _USE_CASE_HEADER.match(ln) or _QUESTION_LINE.match(ln):
                break

            sa = _SHORT_ANSWER.match(ln)
            fa = _FULL_ANSWER.match(ln)
            simple = _SIMPLE_ANSWER.match(ln)

            if sa:
                short_answer = _continuation_text(lines, i, sa.group("a"))
                i = _skip_continuation(lines, i)
                continue
            if fa:
                full_answer = _continuation_text(lines, i, fa.group("a"))
                i = _skip_continuation(lines, i)
                continue
            if simple and not short_answer and not full_answer:
                full_answer = _continuation_text(lines, i, simple.group("a"))
                i = _skip_continuation(lines, i)
                continue
            if _SOURCES_HEADER.match(ln):
                i += 1
                while i < len(lines):
                    sn = lines[i]
                    if _USE_CASE_HEADER.match(sn) or _QUESTION_LINE.match(sn):
                        break
                    if sn.strip().startswith(("-", "*", "•")):
                        sources_lines.append(sn.strip())
                    elif sn.strip().startswith("**"):
                        # Hit a new labelled field — back up and re-handle.
                        break
                    i += 1
                continue
            i += 1

        body = _stitch_answer(short_answer, full_answer, sources_lines)
        if question and body:
            out.append(
                ParsedFAQ(
                    question=question,
                    answer=body,
                    use_case=current_use_case,
                    module_name=current_module,
                )
            )

    return out


def _continuation_text(lines: list[str], start: int, first_value: str) -> str:
    """Gather the text on the matched line plus subsequent non-empty,
    non-labelled lines until the next labelled field or blank gap."""
    parts: list[str] = [first_value.strip()]
    j = start + 1
    while j < len(lines):
        nxt = lines[j]
        stripped = nxt.strip()
        if not stripped:
            break
        if (
            _USE_CASE_HEADER.match(nxt)
            or _QUESTION_LINE.match(nxt)
            or _SHORT_ANSWER.match(nxt)
            or _FULL_ANSWER.match(nxt)
            or _SIMPLE_ANSWER.match(nxt)
            or _SOURCES_HEADER.match(nxt)
            or stripped.startswith("**")
            or stripped.startswith("---")
            or stripped.startswith("***")
            or stripped.startswith("# ")
        ):
            break
        parts.append(stripped)
        j += 1
    return " ".join(p for p in parts if p).strip()


def _skip_continuation(lines: list[str], start: int) -> int:
    """Advance past the continuation lines that `_continuation_text` consumed."""
    j = start + 1
    while j < len(lines):
        nxt = lines[j]
        stripped = nxt.strip()
        if not stripped:
            break
        if (
            _USE_CASE_HEADER.match(nxt)
            or _QUESTION_LINE.match(nxt)
            or _SHORT_ANSWER.match(nxt)
            or _FULL_ANSWER.match(nxt)
            or _SIMPLE_ANSWER.match(nxt)
            or _SOURCES_HEADER.match(nxt)
            or stripped.startswith("**")
            or stripped.startswith("---")
            or stripped.startswith("***")
            or stripped.startswith("# ")
        ):
            break
        j += 1
    return j


def _stitch_answer(
    short_answer: str, full_answer: str, sources: Iterable[str]
) -> str:
    """Combine the short answer, full answer, and source list into a
    single string suitable for the FAQ row. Short answer first when it
    exists (gives the synthesis layer a one-liner to lead with)."""
    parts: list[str] = []
    if short_answer:
        parts.append(short_answer)
    if full_answer and full_answer != short_answer:
        if short_answer:
            parts.append("")  # blank line between short + full
        parts.append(full_answer)
    sources_list = [s for s in sources if s.strip()]
    if sources_list:
        parts.append("")
        parts.append("Sources:")
        parts.extend(sources_list)
    return "\n".join(parts).strip()


def _module_for_use_case(use_case: str) -> Optional[str]:
    needle = use_case.lower()
    for key, module in _USE_CASE_TO_MODULE.items():
        if key in needle:
            return module
    return None


async def import_faqs(
    *,
    text: str,
    faq_store: FAQStore,
    source_filename: str = "",
    owner_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> int:
    """Parse the markdown library and write each entry to the FAQ
    store. Returns the count of FAQs imported.

    The caller decides whether to scope to a project or import as
    library-wide. Use-case-aware module scoping is automatic."""
    parsed = parse_faq_markdown(text)
    for entry in parsed:
        await faq_store.create(
            question=entry.question,
            answer=entry.answer,
            module_name=entry.module_name,
            project_id=project_id,
            source_filename=source_filename,
            owner_id=owner_id,
        )
    return len(parsed)


async def seed_default_faqs_if_empty(faq_store: FAQStore) -> int:
    """Auto-seed the bundled CEN FAQ Library v2 on first startup.

    The deployed Render config uses ``CEN_DB_PATH=/tmp/cen.db`` which
    resets on every deploy — without seeding, the FAQ store is empty
    and the concierge has nothing to ground against. We import as
    global FAQs (``owner_id=None``) so every operator can see them
    while still respecting per-module scoping.

    Idempotent: only seeds when the table is empty, so a user who
    has already imported their own library is never overwritten.
    Returns the count seeded (0 when skipped).
    """
    from pathlib import Path

    existing = await faq_store.list_all()
    if existing:
        return 0

    seed_path = (
        Path(__file__).resolve().parent.parent / "seed" / "faq_library.md"
    )
    if not seed_path.exists():
        return 0

    text = seed_path.read_text(encoding="utf-8")
    return await import_faqs(
        text=text,
        faq_store=faq_store,
        source_filename="faq_library.md (bundled seed)",
        owner_id=None,
    )
