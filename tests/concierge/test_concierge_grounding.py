"""Grounding tests — relevance floor, field retrieval, lead selection.

Regression suite for the reported failure: a navigator on "Household
Data Collection" asked what "How many people live in the household?"
meant and was answered with a paragraph about requesting environmental
exposure records, prefixed with the step name so it read authoritative.
"""

from __future__ import annotations

import pytest

from cen.core.concierge_grounding import (
    MIN_FAQ_LEAD_SCORE,
    RetrievedChunk,
    describe_pending_step,
    has_useful_grounding,
    retrieve_input_fields,
    select_lead,
)
from cen.core.models import (
    ConciergeCitation,
    InputField,
    Session,
    SessionStatus,
)


def _case_on_household_step() -> Session:
    return Session(
        id="case1",
        module_name="charity_care_navigator",
        status=SessionStatus.AWAITING_INPUT,
        pending_node="household_data_collection",
        pending_input_fields=[
            InputField(
                key="household_size",
                label="How many people live in the household?",
                type="number",
                required=True,
                description=(
                    "Count everyone who lives there, including children "
                    "and dependents."
                ),
            ),
            InputField(
                key="annual_income",
                label="Annual household income",
                type="number",
                required=True,
                description="Total before-tax income for the past year.",
            ),
        ],
    )


def _chunk(kind: str, score: float, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        text=text,
        score=score,
        citation=ConciergeCitation(kind=kind, question=text[:40], score=score),
    )


class TestRetrieveInputFields:
    def test_matches_the_field_the_question_is_about(self):
        case = _case_on_household_step()

        chunks = retrieve_input_fields(
            case=case, question='what does it mean "how many people in household?"'
        )

        assert chunks, "the asked-about field must be retrieved"
        top = chunks[0]
        # The authored description is the answer to this question.
        assert "Count everyone who lives there" in top.text
        assert top.citation.kind == "input_field"

    def test_matched_field_outranks_a_weak_faq(self):
        """The whole point: field beats an unrelated FAQ."""
        case = _case_on_household_step()

        field_chunks = retrieve_input_fields(
            case=case, question="how many people live in the household"
        )
        noise = _chunk("faq", 0.24, "What does the AI Concierge do at Ongoing Monitoring?")

        lead = select_lead(field_chunks + [noise])

        assert lead is not None
        assert lead.citation.kind == "input_field"

    def test_unrelated_question_matches_no_field(self):
        case = _case_on_household_step()

        chunks = retrieve_input_fields(
            case=case, question="what is the weather in Chicago"
        )

        assert chunks == []

    def test_no_pending_fields_returns_empty(self):
        case = Session(
            id="case2",
            module_name="charity_care_navigator",
            status=SessionStatus.ACTIVE,
        )

        assert retrieve_input_fields(case=case, question="anything") == []

    def test_none_case_returns_empty(self):
        assert retrieve_input_fields(case=None, question="anything") == []

    def test_empty_question_returns_empty(self):
        case = _case_on_household_step()

        assert retrieve_input_fields(case=case, question="") == []


class TestSelectLead:
    def test_respects_score_over_kind(self):
        """The exact inversion that caused the bad answer.

        Current-step context scored 0.95, the irrelevant FAQ 0.24, and
        the old rule picked the FAQ purely because it was an FAQ.
        """
        step = _chunk("workflow", 0.95, "Current step: Household Data Collection.")
        bad_faq = _chunk("faq", 0.24, "What does the AI Concierge do at Ongoing Monitoring?")

        lead = select_lead([bad_faq, step])

        assert lead is step

    def test_strong_faq_may_lead(self):
        strong = _chunk("faq", 0.41, "Charity care is free or reduced-cost care...")
        weak_step = _chunk("workflow", 0.20, "Current step: something.")

        assert select_lead([weak_step, strong]) is strong

    def test_faq_below_floor_cannot_lead(self):
        below = _chunk("faq", MIN_FAQ_LEAD_SCORE - 0.01, "noise")

        assert select_lead([below]) is None

    def test_faq_at_floor_can_lead(self):
        at = _chunk("faq", MIN_FAQ_LEAD_SCORE, "just good enough")

        assert select_lead([at]) is at

    def test_non_faq_kinds_are_not_floored(self):
        """Step context is authored for this case — always eligible."""
        step = _chunk("workflow", 0.10, "Current step: something.")

        assert select_lead([step]) is step

    def test_empty_returns_none(self):
        assert select_lead([]) is None


class TestHasUsefulGrounding:
    def test_false_when_only_noise(self):
        noise = [_chunk("faq", 0.24, "a"), _chunk("faq", 0.21, "b")]

        assert has_useful_grounding(noise) is False

    def test_true_when_something_clears_the_floor(self):
        chunks = [_chunk("faq", 0.24, "a"), _chunk("faq", 0.38, "b")]

        assert has_useful_grounding(chunks) is True

    def test_false_when_empty(self):
        assert has_useful_grounding([]) is False


class TestDescribePendingStep:
    def test_lists_multiple_fields(self):
        recap = describe_pending_step(_case_on_household_step())

        assert recap is not None
        assert "How many people live in the household?" in recap
        assert "Annual household income" in recap
        assert " and " in recap

    def test_single_field_has_no_list_join(self):
        case = Session(
            id="case3",
            module_name="m",
            status=SessionStatus.AWAITING_INPUT,
            pending_input_fields=[
                InputField(key="patient_name", label="Patient name", type="text")
            ],
        )

        assert describe_pending_step(case) == (
            "Right now this step is asking for: Patient name."
        )

    def test_none_when_no_fields(self):
        case = Session(id="case4", module_name="m", status=SessionStatus.ACTIVE)

        assert describe_pending_step(case) is None

    def test_none_case(self):
        assert describe_pending_step(None) is None


class TestReportedFailureEndToEnd:
    """The exact interaction the user reported, through answer_question.

    Navigator on "Household Data Collection" asks what the household
    field means; the library contains meta-FAQs about the product whose
    titles ("What does the AI Concierge do when...") share only
    stopwords with the question but used to win retrieval and be
    asserted as the answer.
    """

    @pytest.fixture
    async def store_with_decoys(self):
        from cen.core.faq_store import FAQStore

        store = FAQStore(":memory:")
        await store.initialize()
        await store.create(
            question=(
                "What does the AI Concierge do when I'm at the Ongoing "
                "Monitoring stage — is it still useful?"
            ),
            answer=(
                "The AI Concierge can explain how to request environmental "
                "test records from government agencies, describe what medical "
                "documentation is typically needed for specific exposure "
                "types, and help you draft records request letters."
            ),
            module_name="charity_care_navigator",
            owner_id="user1",
        )
        await store.create(
            question=(
                "How does the AI Concierge help during the billing error "
                "review step — what can I ask it?"
            ),
            answer="It can walk you through the billing error review step.",
            module_name="charity_care_navigator",
            owner_id="user1",
        )
        yield store
        await store.close()

    @pytest.fixture
    async def chat(self):
        from cen.core.chat_store import ChatMessageStore

        store = ChatMessageStore(":memory:")
        await store.initialize()
        yield store
        await store.close()

    async def test_field_question_is_answered_from_the_field(
        self, store_with_decoys, chat
    ):
        from cen.core.concierge import answer_question

        resp = await answer_question(
            'what does it mean "how many people in household?"',
            faq_store=store_with_decoys,
            chat_store=chat,
            case=_case_on_household_step(),
            owner_id="user1",
        )

        # The authored field description answers it.
        assert "Count everyone who lives there" in resp.answer
        # The environmental-records paragraph must not appear.
        assert "environmental test records" not in resp.answer
        assert "exposure" not in resp.answer

    async def test_unanswerable_question_says_so(self, store_with_decoys, chat):
        """Stopword-only overlap must not be asserted as an answer."""
        from cen.core.concierge import answer_question

        resp = await answer_question(
            "what does it mean when the sky turns green",
            faq_store=store_with_decoys,
            chat_store=chat,
            case=None,
            owner_id="user1",
        )

        assert resp.mode == "no_match"
        assert "environmental test records" not in resp.answer

    async def test_no_match_still_tells_the_navigator_what_is_needed(
        self, store_with_decoys, chat
    ):
        from cen.core.concierge import answer_question

        resp = await answer_question(
            "what does it mean when the sky turns green",
            faq_store=store_with_decoys,
            chat_store=chat,
            case=_case_on_household_step(),
            owner_id="user1",
        )

        assert resp.mode == "no_match"
        assert "How many people live in the household?" in resp.answer


class TestLeadEligibility:
    """Case-state chunks are context, never the answer.

    Their 0.95 is an inclusion priority ("the model must know where we
    are"), not a relevance score. Ranking on it answered "what is
    charity care?" with "Current step: Collect household income."
    """

    def test_context_chunk_cannot_lead_over_a_relevant_faq(self):
        state = RetrievedChunk(
            text="Current step: Collect household income.",
            score=0.95,
            lead_eligible=False,
            citation=ConciergeCitation(kind="workflow", question="Current step", score=0.95),
        )
        faq = _chunk("faq", 0.577, "Charity care is free or reduced-cost care...")

        assert select_lead([state, faq]) is faq

    def test_context_chunk_alone_is_not_useful_grounding(self):
        state = RetrievedChunk(
            text="Current step: Collect household income.",
            score=0.95,
            lead_eligible=False,
            citation=ConciergeCitation(kind="workflow", question="Current step", score=0.95),
        )

        assert has_useful_grounding([state]) is False
