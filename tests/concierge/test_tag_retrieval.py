"""Concierge retrieval wiring for tags: step tags boost matching FAQs,
and faq_pin ids are always surfaced regardless of match."""

from __future__ import annotations

import pytest

from cen.core.concierge import _retrieve_faqs
from cen.core.faq_store import FAQStore


@pytest.fixture()
async def store():
    s = FAQStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestTagRetrieval:
    async def test_step_tags_boost_matching_faq(self, store: FAQStore):
        tagged = await store.create(
            question="Program overview.",
            answer="Notes about the eligibility process.",
            tags=["function:eligibility_check", "domain:charity_care"],
        )
        chunks = await _retrieve_faqs(
            question="eligibility",
            faq_store=store,
            module_name=None,
            project_id=None,
            owner_id=None,
            boost_tags=["function:eligibility_check"],
        )
        assert any(c.citation.faq_id == tagged.id for c in chunks)

    async def test_faq_pin_always_surfaces(self, store: FAQStore):
        # A pinned FAQ with zero lexical overlap with the question must
        # still appear, and lead the FAQ chunks.
        pinned = await store.create(
            question="Parking validation.",
            answer="Where to validate parking at the clinic.",
            tags=[],
        )
        chunks = await _retrieve_faqs(
            question="how do I appeal a denial",
            faq_store=store,
            module_name=None,
            project_id=None,
            owner_id=None,
            pin_ids=[pinned.id],
        )
        assert chunks, "pinned FAQ should surface even with no lexical match"
        assert chunks[0].citation.faq_id == pinned.id

    async def test_pin_not_duplicated_when_also_matched(self, store: FAQStore):
        faq = await store.create(
            question="How do I appeal a denial?",
            answer="File a level-one internal appeal within 180 days.",
            tags=[],
        )
        chunks = await _retrieve_faqs(
            question="how do I appeal a denial",
            faq_store=store,
            module_name=None,
            project_id=None,
            owner_id=None,
            pin_ids=[faq.id],
        )
        matching = [c for c in chunks if c.citation.faq_id == faq.id]
        assert len(matching) == 1  # pinned + lexical match deduped
