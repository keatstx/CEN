"""Unit tests for FAQStore + the lightweight TF-IDF retrieval."""

from __future__ import annotations

import pytest

from cen.core.faq_store import FAQStore


@pytest.fixture()
async def store():
    s = FAQStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestFAQStoreCRUD:
    async def test_create_and_get(self, store: FAQStore):
        faq = await store.create(
            question="How do I qualify for charity care?",
            answer="Charity care is available if your income is below 200% of the FPL.",
            module_name="charity_care_navigator",
            owner_id="alice",
        )
        assert faq.id
        assert faq.module_name == "charity_care_navigator"
        fetched = await store.get(faq.id)
        assert fetched is not None
        assert fetched.question == "How do I qualify for charity care?"

    async def test_list_all_global(self, store: FAQStore):
        await store.create(
            question="Global FAQ",
            answer="Applies to every workflow.",
        )
        results = await store.list_all()
        assert len(results) == 1
        assert results[0].module_name is None

    async def test_list_filtered_by_module(self, store: FAQStore):
        await store.create(
            question="Charity Q",
            answer="A1",
            module_name="charity_care_navigator",
        )
        await store.create(
            question="Appeal Q",
            answer="A2",
            module_name="insurance_appeal_assistant",
        )
        await store.create(question="Global Q", answer="A3")  # global
        results = await store.list_all(module_name="charity_care_navigator")
        # Charity FAQ + global FAQ.
        assert len(results) == 2
        assert {r.question for r in results} == {"Charity Q", "Global Q"}

    async def test_list_filtered_by_project(self, store: FAQStore):
        await store.create(
            question="Project-specific",
            answer="A",
            project_id="proj-1",
        )
        await store.create(question="Global", answer="B")
        results = await store.list_all(project_id="proj-1")
        assert len(results) == 2

    async def test_delete(self, store: FAQStore):
        faq = await store.create(question="Q", answer="A")
        assert await store.delete(faq.id) is True
        assert await store.get(faq.id) is None


class TestFAQRetrieval:
    async def test_search_returns_best_match_first(self, store: FAQStore):
        await store.create(
            question="What is a deductible?",
            answer="A deductible is the amount you owe before insurance pays.",
        )
        await store.create(
            question="How do I file an appeal?",
            answer="You write a letter to your insurance company.",
        )
        results = await store.search("explain deductible to me")
        assert len(results) >= 1
        top_faq, _ = results[0]
        assert "deductible" in top_faq.question.lower()

    async def test_search_returns_empty_for_no_match(self, store: FAQStore):
        await store.create(
            question="What is a deductible?",
            answer="The amount you owe before insurance pays.",
        )
        results = await store.search("how to bake bread")
        # Below the min_score threshold — no false matches.
        assert results == []

    async def test_search_respects_module_scope(self, store: FAQStore):
        await store.create(
            question="What is appeal?",
            answer="A",
            module_name="insurance_appeal_assistant",
        )
        await store.create(
            question="What is appeal?",
            answer="B",
            module_name="charity_care_navigator",
        )
        # Searching with module=insurance_appeal_assistant should only
        # see the appeal-scoped FAQ + global ones (none here).
        results = await store.search(
            "appeal", module_name="insurance_appeal_assistant"
        )
        assert len(results) == 1
        assert results[0][0].answer == "A"

    async def test_search_top_k_limit(self, store: FAQStore):
        for i in range(10):
            await store.create(
                question=f"Question about insurance topic {i}",
                answer=f"Answer {i}",
            )
        results = await store.search("insurance", top_k=3)
        assert len(results) <= 3

    async def test_search_empty_query_returns_empty(self, store: FAQStore):
        await store.create(question="Q", answer="A")
        assert await store.search("") == []

    async def test_search_scores_descending(self, store: FAQStore):
        await store.create(
            question="What is charity care?",
            answer="A program for low-income patients.",
        )
        await store.create(
            question="How do I apply for charity care?",
            answer="Submit the form at the billing office.",
        )
        results = await store.search("apply charity care application")
        assert len(results) >= 2
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)
