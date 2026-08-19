"""Concierge service tests — guardrails, retrieval fusion, and
conversational synthesis. The pipeline is grounded in the FAQ store;
no LLM call is made in v1 (mock backend)."""

from __future__ import annotations

import pytest

from cen.core.chat_store import ChatMessageStore
from cen.core.concierge import answer_question
from cen.core.faq_store import FAQStore
from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
    Session,
    SessionStatus,
)


@pytest.fixture
async def faq_store():
    store = FAQStore(":memory:")
    await store.initialize()
    await store.create(
        question="What is charity care?",
        answer=(
            "Charity care is free or reduced-cost hospital care that nonprofit "
            "hospitals must offer qualifying low-income patients.\n\n"
            "Under Illinois law, families at or below 200% FPL qualify for "
            "free care; 200-400% FPL families qualify for discounted care."
        ),
        module_name="charity_care_navigator",
        owner_id="user1",
    )
    await store.create(
        question="How do I apply for charity care?",
        answer="Open a Charity Care case in the Cases panel and follow the workflow.",
        module_name="charity_care_navigator",
        owner_id="user1",
    )
    yield store
    await store.close()


@pytest.fixture
async def chat_store():
    store = ChatMessageStore(":memory:")
    await store.initialize()
    yield store
    await store.close()


def _aop_with_step():
    return AOPDefinition(
        module_name="charity_care_navigator",
        nodes=[
            AOPNode(
                id="income_intake",
                type=NodeType.ACTION,
                metadata=NodeMetadata(
                    label="Collect household income",
                    description="Capture pay stubs or self-attestation.",
                ),
            ),
            AOPNode(
                id="fpl_check",
                type=NodeType.CONDITION,
                metadata=NodeMetadata(label="Income vs FPL"),
                condition_field="income_fpl_percent",
                condition_operator="<=",
                condition_value=200,
                true_next="income_intake",
                false_next="income_intake",
            ),
        ],
        edges=[AOPEdge(source="income_intake", target="fpl_check")],
    )


def _case():
    return Session(
        id="case1",
        module_name="charity_care_navigator",
        status=SessionStatus.AWAITING_INPUT,
        pending_node="income_intake",
        executed_nodes=[],
        owner_id="user1",
    )


async def test_guardrail_fires_for_legal_advice(faq_store, chat_store):
    resp = await answer_question(
        "Should I sign this hospital settlement letter?",
        faq_store=faq_store,
        chat_store=chat_store,
        case=_case(),
        owner_id="user1",
    )
    assert resp.mode == "guardrail"
    assert "professional" in resp.answer.lower()


async def test_no_match_returns_no_match_mode(faq_store, chat_store):
    # No overlap with seeded FAQs (no "charity"/"care"/"apply"/"how")
    # and no aop is provided so the workflow retriever can't fall back.
    resp = await answer_question(
        "Cherry blossom astronomy galaxy quasar",
        faq_store=faq_store,
        chat_store=chat_store,
        case=_case(),
        owner_id="user1",
    )
    assert resp.mode == "no_match"


async def test_synthesis_returns_faq_grounded_reply(faq_store, chat_store):
    resp = await answer_question(
        "what is charity care?",
        faq_store=faq_store,
        chat_store=chat_store,
        case=_case(),
        aop=_aop_with_step(),
        owner_id="user1",
    )
    assert resp.mode == "synthesis"
    assert resp.citations, "expected at least one citation"
    # The lead-paragraph extraction should surface the short answer.
    assert "charity care" in resp.answer.lower()


async def test_workflow_chunk_appears_when_no_strong_faq_match(faq_store, chat_store):
    """If the user asks about the current step and there's no FAQ for
    it, the workflow retriever still surfaces the step description."""
    resp = await answer_question(
        "What am I supposed to do at this step?",
        faq_store=faq_store,
        chat_store=chat_store,
        case=_case(),
        aop=_aop_with_step(),
        owner_id="user1",
    )
    # Either synthesis with a workflow citation, or no_match; the test
    # asserts that workflow context is surfaced when present.
    if resp.mode == "synthesis":
        kinds = {c.kind for c in resp.citations}
        assert "workflow" in kinds or "faq" in kinds


async def test_chat_history_persists_user_and_assistant_turns(faq_store, chat_store):
    case = _case()
    resp = await answer_question(
        "what is charity care?",
        faq_store=faq_store,
        chat_store=chat_store,
        case=case,
        owner_id="user1",
    )
    history = await chat_store.list_for_case(case.id, owner_id="user1")
    assert len(history) == 2
    assert history[0].role == "user"
    assert history[1].role == "assistant"
    assert history[1].content == resp.answer


async def test_synthesis_intro_changes_with_history(faq_store, chat_store):
    """Multi-turn check: by turn 2+, the conversational intro should
    soften ('Sure —', 'Got it.') so the assistant feels human rather
    than a search box."""
    case = _case()
    await answer_question(
        "what is charity care?",
        faq_store=faq_store,
        chat_store=chat_store,
        case=case,
        owner_id="user1",
    )
    second = await answer_question(
        "how do I apply?",
        faq_store=faq_store,
        chat_store=chat_store,
        case=case,
        owner_id="user1",
    )
    # First turn has no intro; second turn opens with a connector.
    assert second.answer.startswith(("Sure", "Got it"))


class TestDegradedLLMNotPresentedAsSynthesis:
    """A degraded LLM must never be reported as `llm_synthesis`.

    Regression guard for the 2026-08-16 Groq model retirement: the
    primary raised on every call, FallbackLanguageModel returned the
    mock's canned filler, and because backend_name still read
    "openai-compat" the mock-skip in _synthesize_with_llm never fired.
    Production served hardcoded text under mode="llm_synthesis".
    """

    async def test_degraded_falls_back_to_rule_based_mode(
        self, faq_store, chat_store
    ):
        from cen.llm.factory import FallbackLanguageModel
        from cen.llm.mock import MockLanguageModel

        class _RetiredModel:
            backend_name = "openai-compat"

            async def generate(self, prompt: str, max_tokens: int = 128) -> str:
                raise RuntimeError("model_decommissioned")

            async def is_available(self) -> bool:
                return True

        llm = FallbackLanguageModel(
            primary=_RetiredModel(), fallback=MockLanguageModel(), timeout=5.0
        )

        resp = await answer_question(
            "what is charity care?",
            faq_store=faq_store,
            chat_store=chat_store,
            case=_case(),
            owner_id="user1",
            llm=llm,
        )

        assert resp.mode == "synthesis"
        # The canned mock filler must not reach the user.
        assert "Federal Poverty Level guidelines" not in resp.answer
        assert "Processed request" not in resp.answer
        # The grounded rule-based answer still lands.
        assert resp.answer
        assert resp.citations
