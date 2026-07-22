"""FAQ function-tagging: heuristic classifier, import attaches function
tags, and the end-to-end step-scoped boost fires with from_step marked."""

from __future__ import annotations

import pytest

from cen.core.concierge import _retrieve_faqs
from cen.core.faq_classify import heuristic_function
from cen.core.faq_import import import_faqs
from cen.core.faq_store import FAQStore

_MD = """# Use Case 1: Charity Care

### Stage: Awareness

**Q1: Who is eligible for charity care?**
**A (Short):** Households below 200% of the Federal Poverty Level.

**Q2: How do I check the status of a submitted application?**
**A (Short):** Poll the hospital's determination line weekly.
"""


class TestHeuristicClassifier:
    def test_eligibility_question_maps_to_function(self):
        assert heuristic_function("Who is eligible for charity care?", "") == (
            "function:eligibility_check"
        )

    def test_unrelated_question_maps_to_none(self):
        assert heuristic_function("What is the weather today?", "") is None


@pytest.fixture()
async def store():
    s = FAQStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestImportAttachesFunctionTags:
    async def test_import_tags_via_heuristic(self, store: FAQStore):
        n = await import_faqs(text=_MD, faq_store=store)
        assert n == 2
        faqs = await store.list_all()
        by_q = {f.question: f.tags for f in faqs}
        assert "function:eligibility_check" in by_q["Who is eligible for charity care?"]

    async def test_step_scoped_boost_fires_end_to_end(self, store: FAQStore):
        await import_faqs(text=_MD, faq_store=store)
        # A navigator on an eligibility_check step asks a vague question.
        chunks = await _retrieve_faqs(
            question="eligibility",
            faq_store=store,
            module_name="charity_care_navigator",
            project_id=None,
            owner_id=None,
            boost_tags=["function:eligibility_check"],
        )
        elig = [c for c in chunks if "eligible" in c.citation.question.lower()]
        assert elig, "eligibility FAQ should surface on an eligibility-tagged step"
        assert elig[0].citation.from_step is True
