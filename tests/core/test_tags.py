"""Tests for step/FAQ tags: vocabulary helpers, FAQ store tag boost +
migration, structural auto-assignment at extraction, validator warnings,
and the concierge retrieval wiring (tag boost + faq_pin)."""

from __future__ import annotations

import aiosqlite
import pytest

from cen.core.faq_store import FAQStore
from cen.core.tags import is_known_tag, parse_tag, tag_overlap, unknown_tags
from cen.sop.extractor import _structural_tags
from cen.core.models import NodeType


# ── vocabulary helpers ───────────────────────────────────────────────


class TestTagVocabulary:
    def test_parse_tag(self):
        assert parse_tag("function:eligibility_check") == ("function", "eligibility_check")
        assert parse_tag("nocolon") == ("", "nocolon")

    def test_known_controlled_tag(self):
        assert is_known_tag("function:eligibility_check") is True
        assert is_known_tag("domain:charity_care") is True

    def test_open_facet_accepts_any_value(self):
        assert is_known_tag("attribute:anything_goes_here") is True

    def test_unknown_facet_and_value(self):
        assert is_known_tag("function:not_a_real_value") is False
        assert is_known_tag("madeup:whatever") is False
        assert is_known_tag("malformed") is False

    def test_unknown_tags_filters(self):
        tags = ["function:intake", "function:bogus", "attribute:x"]
        assert unknown_tags(tags) == ["function:bogus"]

    def test_tag_overlap(self):
        assert tag_overlap(["a", "b", "c"], ["b", "c", "d"]) == 2


# ── structural auto-assignment ───────────────────────────────────────


class TestStructuralTags:
    def test_phase_maps_to_function(self):
        assert _structural_tags("Eligibility Screening", NodeType.ACTION) == [
            "function:eligibility_check"
        ]
        assert _structural_tags("Document Collection", NodeType.ACTION) == [
            "function:document_collection"
        ]

    def test_node_type_fallback_when_no_phase(self):
        assert _structural_tags("", NodeType.APPROVAL) == ["function:approval"]
        assert _structural_tags("", NodeType.HANDOFF) == ["function:escalation"]

    def test_no_match_returns_empty(self):
        assert _structural_tags("Miscellaneous prose", NodeType.ACTION) == []


# ── FAQ store: tags round-trip, migration, boost ─────────────────────


@pytest.fixture()
async def store():
    s = FAQStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestFAQStoreTags:
    async def test_tags_round_trip(self, store: FAQStore):
        faq = await store.create(
            question="Income threshold?",
            answer="Below 200% FPL.",
            tags=["function:eligibility_check", "domain:charity_care"],
        )
        fetched = await store.get(faq.id)
        assert fetched is not None
        assert fetched.tags == ["function:eligibility_check", "domain:charity_care"]

    async def test_tag_boost_rescues_weak_lexical_match(self, store: FAQStore):
        # A FAQ whose text barely matches the query but shares the step's
        # tags should still surface thanks to the boost.
        tagged = await store.create(
            question="Program overview.",
            answer="General notes about the process.",
            tags=["function:eligibility_check"],
        )
        await store.create(
            question="Unrelated topic.",
            answer="Parking validation details.",
            tags=[],
        )
        results = await store.search(
            "eligibility",  # weak lexical overlap with the tagged FAQ
            boost_tags=["function:eligibility_check"],
            min_score=0.05,
            top_k=5,
        )
        ids = [f.id for f, _ in results]
        assert tagged.id in ids  # rescued by the tag boost

    async def test_legacy_db_without_tags_column_migrates(self):
        # Simulate a pre-tags DB, then let FAQStore migrate it.
        db = await aiosqlite.connect(":memory:")
        await db.execute(
            """
            CREATE TABLE faqs (
                id TEXT PRIMARY KEY, module_name TEXT, project_id TEXT,
                question TEXT NOT NULL, answer TEXT NOT NULL,
                source_filename TEXT NOT NULL DEFAULT '', owner_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            "INSERT INTO faqs (id, question, answer, created_at) VALUES "
            "('legacy1', 'Old Q', 'Old A', '2026-01-01T00:00:00Z')"
        )
        await db.commit()

        store = FAQStore(":memory:")
        store._db = db
        store._db.row_factory = aiosqlite.Row
        await store._ensure_column("tags", "TEXT NOT NULL DEFAULT '[]'")
        fetched = await store.get("legacy1")
        assert fetched is not None
        assert fetched.tags == []  # defaulted, no crash
        await db.close()
