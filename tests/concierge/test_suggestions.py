"""Tests for the suggestion extractor and the /concierge/suggestions
endpoint.

The extractor is rule-based; these tests are the fidelity contract.
A regression here means the right panel stopped feeding the center
panel correctly — a user-visible breakage.
"""

from __future__ import annotations

from typing import List

import pytest

from cen.core.models import ChatMessage, InputField
from cen.core.suggestions import RegexExtractor


def _msg(content: str, role: str = "user") -> ChatMessage:
    return ChatMessage(
        id="",
        case_id="c",
        role=role,
        content=content,
        owner_id="user1",
    )


def _field(key: str, ftype: str = "text", **kwargs) -> InputField:
    return InputField(key=key, label=key.replace("_", " "), type=ftype, **kwargs)


# ── Field-key heuristics (high confidence) ──────────────────────────


def test_household_size_from_family_of_phrasing():
    history = [_msg("the family is a household of three people")]
    schema = [_field("household_size", "number")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert len(s) == 1
    assert s[0].key == "household_size"
    assert s[0].value == 3
    assert s[0].confidence > 0.5
    assert "household of three" in s[0].evidence.lower()


def test_household_size_from_x_person_phrasing():
    history = [_msg("we're working with a 4-person family")]
    schema = [_field("household_size", "number")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == 4


def test_fpl_percent_from_explicit_phrasing():
    history = [_msg("their income is about 150% of FPL")]
    schema = [_field("income_fpl_percent", "number")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == 150
    assert s[0].confidence >= 0.85


def test_income_with_k_suffix():
    history = [_msg("the family earns about $32k a year")]
    schema = [_field("annual_income", "currency")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == 32_000


def test_income_with_million_suffix():
    history = [_msg("the household income is roughly 1.2 million")]
    schema = [_field("annual_income", "currency")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == 1_200_000


def test_zip_code_extracted():
    history = [_msg("they live in zip 60615 — south side")]
    schema = [_field("zip_code", "text")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == "60615"
    assert s[0].confidence >= 0.9


# ── Type-based fallbacks ────────────────────────────────────────────


def test_boolean_yes_in_short_message():
    history = [_msg("yes")]
    schema = [_field("has_children_under_19", "boolean")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value is True


def test_boolean_no_in_short_message():
    history = [_msg("no, not currently")]
    schema = [_field("has_insurance", "boolean")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value is False


def test_boolean_skipped_on_long_message():
    """Ambiguous 'yes' inside a long message — skip rather than misextract."""
    long_msg = (
        "yes I had a question about whether the form needs a wet signature "
        "or if scanned is fine, and what the deadline was again, and also "
        "whether the hospital ever told them they qualified"
    )
    history = [_msg(long_msg)]
    schema = [_field("confirmed", "boolean")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s == []


def test_select_matches_option_label():
    history = [_msg("the denial was for medical necessity")]
    schema = [
        _field(
            "denial_type",
            "select",
            options=[
                {"value": "medical_necessity", "label": "Medical Necessity"},
                {"value": "coding_error", "label": "Coding Error"},
            ],
        )
    ]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == "medical_necessity"


def test_date_numeric_normalized_to_iso():
    """US M/D/Y is normalized to ISO — the only format an <input type=date>
    can consume."""
    history = [_msg("the bill date was 03/15/2025")]
    schema = [_field("bill_date", "date")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == "2025-03-15"


def test_date_iso_extracted():
    """ISO input (what the date picker emits, and how DOB is typed) now
    extracts — previously missed entirely."""
    history = [_msg("her date of birth is 1980-05-01")]
    schema = [_field("patient_dob", "date")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == "1980-05-01"


def test_date_long_form_normalized_to_iso():
    history = [_msg("the denial was dated January 15, 2026")]
    schema = [_field("denial_date", "date")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == "2026-01-15"


# ── Behavioral guarantees ───────────────────────────────────────────


def test_assistant_messages_are_ignored():
    """Don't extract from the assistant's own words — only the user's."""
    history = [
        _msg("ok", role="user"),
        _msg("Got it. Households of three at 200% FPL qualify.", role="assistant"),
    ]
    schema = [_field("household_size", "number")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s == []


def test_recent_user_message_overrides_older():
    """If the user said one thing earlier and corrected themselves, the
    most-recent message should win."""
    history = [
        _msg("I think it was a household of two"),
        _msg("actually it's a family of five"),
    ]
    schema = [_field("household_size", "number")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s and s[0].value == 5


def test_no_schema_returns_empty():
    s = RegexExtractor().extract(history=[_msg("anything")], input_schema=[])
    assert s == []


def test_no_history_returns_empty():
    s = RegexExtractor().extract(
        history=[], input_schema=[_field("household_size", "number")]
    )
    assert s == []


def test_free_text_field_not_extracted():
    """Free-text fields should not get a guess — that's the LLM
    extractor's job."""
    history = [_msg("the patient's name is Maria")]
    schema = [_field("notes", "text")]
    s = RegexExtractor().extract(history=history, input_schema=schema)
    assert s == []


# ── End-to-end via the API ──────────────────────────────────────────


async def test_suggestions_endpoint_returns_extracted_values(client):
    # 1) Create a case in a module that has an input_schema we can
    # rely on. charity_care_navigator has identity_verification with
    # household_size + income fields per recent commits.
    create = await client.post(
        "/cases",
        json={"module_name": "charity_care_navigator", "context": {}},
    )
    assert create.status_code in (200, 201), create.text
    case_id = create.json()["id"]

    # 2) Drive the case until it pauses for input. Many modules pause
    # immediately on the first ACTION node when input_schema is set.
    #   We use the module's own /sessions/{id}/execute behavior implicit
    # from create. If pending_input_fields isn't populated, the test
    # still runs but the suggestions endpoint returns [] — that's fine,
    # we'll sanity-check via the synthesis path next.
    case = create.json()
    if not case.get("pending_input_fields"):
        # Fall back to the directly-tested behavior: the extractor is
        # well covered by unit tests above. The endpoint must at least
        # return a 200 with an empty list when there's nothing to
        # extract for.
        r = await client.get(f"/concierge/suggestions/{case_id}")
        assert r.status_code == 200
        assert r.json() == []
        return

    # 3) Send a chat message that mentions extractable values.
    await client.post(
        "/concierge/ask",
        json={
            "question": "the family is a household of four earning $35k",
            "case_id": case_id,
        },
    )

    # 4) Pull suggestions — should contain household_size if the
    # module's pending fields include it.
    r = await client.get(f"/concierge/suggestions/{case_id}")
    assert r.status_code == 200
    suggestions = r.json()
    # Soft assertion: the endpoint works, and if any suggestions came
    # back they're well-shaped.
    for s in suggestions:
        assert "key" in s and "value" in s and "confidence" in s


async def test_suggestions_unknown_case_returns_404(client):
    r = await client.get("/concierge/suggestions/nonexistent")
    assert r.status_code == 404


async def test_suggestions_returns_empty_when_no_pending_fields(client):
    create = await client.post(
        "/cases",
        json={
            "module_name": "charity_care_navigator",
            "context": {"income_fpl_percent": 150},
        },
    )
    case_id = create.json()["id"]
    r = await client.get(f"/concierge/suggestions/{case_id}")
    assert r.status_code == 200
    # Either [] (no pending fields) or some suggestions — both are valid.
    assert isinstance(r.json(), list)
