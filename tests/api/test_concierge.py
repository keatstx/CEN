"""End-to-end tests for the FAQ admin and /concierge/ask endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestFAQAdmin:
    async def test_create_faq(self, client: AsyncClient):
        resp = await client.post(
            "/faqs",
            json={
                "question": "What is a deductible?",
                "answer": "The amount you pay before insurance kicks in.",
                "module_name": "insurance_appeal_assistant",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["question"] == "What is a deductible?"
        assert data["module_name"] == "insurance_appeal_assistant"
        assert data["owner_id"] == "default-operator"

    async def test_list_faqs(self, client: AsyncClient):
        for i in range(3):
            await client.post(
                "/faqs",
                json={"question": f"Q {i}", "answer": f"A {i}"},
            )
        resp = await client.get("/faqs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 3

    async def test_list_filtered_by_module(self, client: AsyncClient):
        await client.post(
            "/faqs",
            json={
                "question": "Charity Q",
                "answer": "Charity A",
                "module_name": "charity_care_navigator",
            },
        )
        await client.post(
            "/faqs",
            json={
                "question": "Appeal Q",
                "answer": "Appeal A",
                "module_name": "insurance_appeal_assistant",
            },
        )
        resp = await client.get(
            "/faqs", params={"module_name": "charity_care_navigator"}
        )
        assert resp.status_code == 200
        # Charity-scoped FAQ; no global ones in this test.
        assert any(f["question"] == "Charity Q" for f in resp.json())
        assert not any(f["question"] == "Appeal Q" for f in resp.json())

    async def test_delete_faq(self, client: AsyncClient):
        create = await client.post(
            "/faqs", json={"question": "Q", "answer": "A"}
        )
        fid = create.json()["id"]
        resp = await client.delete(f"/faqs/{fid}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_faq_404(self, client: AsyncClient):
        assert (await client.delete("/faqs/nope")).status_code == 404


class TestConciergeAsk:
    async def test_returns_matching_faq(self, client: AsyncClient):
        await client.post(
            "/faqs",
            json={
                "question": "What is a deductible?",
                "answer": (
                    "A deductible is the amount you owe out of pocket "
                    "before your insurance starts paying."
                ),
            },
        )
        resp = await client.post(
            "/concierge/ask",
            json={"question": "explain deductible to me"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "deductible" in data["answer"].lower()
        assert data["mode"] == "lookup"
        assert len(data["citations"]) >= 1
        assert data["citations"][0]["score"] > 0

    async def test_no_match_falls_back_to_disclaimer(
        self, client: AsyncClient
    ):
        await client.post(
            "/faqs",
            json={
                "question": "Charity care eligibility threshold",
                "answer": "Below 200% FPL.",
            },
        )
        # Question shares zero non-stopword tokens with the indexed FAQ.
        resp = await client.post(
            "/concierge/ask",
            json={"question": "elephant trampoline accordion"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "couldn't find" in data["answer"].lower()
        assert data["citations"] == []

    async def test_out_of_scope_question_refused_with_guardrail(
        self, client: AsyncClient
    ):
        await client.post(
            "/faqs",
            json={"question": "Q", "answer": "A"},
        )
        resp = await client.post(
            "/concierge/ask",
            json={"question": "should I sue my insurance company"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "guardrail"
        assert "professional" in data["answer"].lower()

    async def test_scoped_to_case_module(self, client: AsyncClient):
        # Create one charity-scoped FAQ and one appeal-scoped FAQ with
        # the same question text. The case is on the appeal module —
        # we should get the appeal answer.
        await client.post(
            "/faqs",
            json={
                "question": "What's next?",
                "answer": "Charity care answer.",
                "module_name": "charity_care_navigator",
            },
        )
        await client.post(
            "/faqs",
            json={
                "question": "What's next?",
                "answer": "Appeal answer.",
                "module_name": "insurance_appeal_assistant",
            },
        )

        # Create a case on the appeal module.
        case = await client.post(
            "/cases", json={"module_name": "insurance_appeal_assistant"}
        )
        cid = case.json()["id"]

        resp = await client.post(
            "/concierge/ask",
            json={"question": "what's next", "case_id": cid},
        )
        assert resp.status_code == 200
        # Should get the appeal-scoped answer, not the charity one.
        assert "appeal" in resp.json()["answer"].lower()

    async def test_unknown_case_404(self, client: AsyncClient):
        resp = await client.post(
            "/concierge/ask",
            json={"question": "anything", "case_id": "does-not-exist"},
        )
        assert resp.status_code == 404
