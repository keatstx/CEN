"""Tests for the FAQ markdown importer.

Uses the real CEN FAQ Library v2 (200 entries) as the fidelity bar —
a regression here means the importer lost ground on the document it's
designed to handle out of the box.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cen.core.faq_import import import_faqs, parse_faq_markdown
from cen.core.faq_store import FAQStore

FIXTURE = Path(__file__).parent / "fixtures" / "faq_library.md"


@pytest.fixture(scope="module")
def library_md() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_parser_emits_two_hundred_entries(library_md: str):
    parsed = parse_faq_markdown(library_md)
    # The library is documented as 200 FAQs across 5 use cases.
    assert len(parsed) == 200, f"expected 200, got {len(parsed)}"


def test_use_case_to_module_mapping(library_md: str):
    parsed = parse_faq_markdown(library_md)
    by_use_case = {entry.use_case for entry in parsed}
    assert "Charity Care" in by_use_case
    assert "Medical Debt" in by_use_case
    # Charity Care entries should pin to charity_care_navigator.
    charity = [p for p in parsed if "charity care" in p.use_case.lower()]
    assert charity, "no Charity Care FAQs parsed"
    assert all(p.module_name == "charity_care_navigator" for p in charity)


def test_each_entry_has_question_and_answer(library_md: str):
    parsed = parse_faq_markdown(library_md)
    for entry in parsed:
        assert entry.question, f"entry missing question: {entry}"
        assert entry.answer, f"entry missing answer: {entry.question}"
        # Answers should include the source list when one was present.
        # (Not all entries have sources, so this is a soft check.)


def test_simple_inline_format_parses_fully():
    """Sanity check on a small synthetic doc independent of the
    real fixture so a regression in the parser is debuggable."""
    md = (
        "# Use Case 1: Charity Care\n\n"
        "**Q1: First question?**\n"
        "**A (Short):** Short reply.\n"
        "**A (Full):** Full reply with detail.\n"
        "**Sources:**\n"
        "- [Source one](https://example.com/1)\n"
        "- [Source two](https://example.com/2)\n\n"
        "---\n\n"
        "**Q2: Second question?**\n"
        "**A (Short):** Just the short.\n"
    )
    parsed = parse_faq_markdown(md)
    assert len(parsed) == 2
    assert parsed[0].question == "First question?"
    assert "Short reply." in parsed[0].answer
    assert "Full reply with detail." in parsed[0].answer
    assert "https://example.com/1" in parsed[0].answer
    assert parsed[0].module_name == "charity_care_navigator"
    assert parsed[1].question == "Second question?"


async def test_import_writes_to_store(library_md: str):
    store = FAQStore(":memory:")
    await store.initialize()
    try:
        count = await import_faqs(
            text=library_md,
            faq_store=store,
            source_filename="faq_library.md",
            owner_id="test_user",
        )
        assert count == 200
        # Spot-check: charity-care FAQs should be retrievable when
        # scoped to the matching module.
        results = await store.search(
            "charity care eligibility",
            module_name="charity_care_navigator",
            owner_id="test_user",
            top_k=5,
        )
        assert results, "no FAQs matched a charity-care query"
    finally:
        await store.close()
