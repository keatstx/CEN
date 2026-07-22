"""Tests for the LLM-backed suggestion extractor.

Contract: regex is trusted for structured fields; the LLM only fills
gaps (free-text like names); any LLM failure degrades to the pure regex
result; the chat is scrubbed before it reaches the LLM.
"""

from __future__ import annotations

import pytest

from cen.core.models import ChatMessage, InputField
from cen.core.suggestions_llm import LLMExtractor


class _FakeLLM:
    def __init__(self, response: str = "", raises: bool = False) -> None:
        self._response = response
        self._raises = raises
        self.calls: list[str] = []

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        self.calls.append(prompt)
        if self._raises:
            raise RuntimeError("llm down")
        return self._response

    @property
    def backend_name(self) -> str:
        return "fake"


def _msg(content: str) -> ChatMessage:
    return ChatMessage(id="", case_id="c", role="user", content=content, owner_id="u")


def _field(key: str, ftype: str = "text", **kw) -> InputField:
    return InputField(key=key, label=key.replace("_", " "), type=ftype, **kw)


@pytest.mark.asyncio
async def test_llm_fills_free_text_name_gap():
    llm = _FakeLLM('{"patient_name": "Maria Lopez"}')
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("the patient's name is Maria Lopez")],
        input_schema=[_field("patient_name", "text")],
    )
    assert len(out) == 1
    assert out[0].key == "patient_name" and out[0].value == "Maria Lopez"
    assert out[0].confidence >= 0.5  # auto-applies in ChatLedStep


@pytest.mark.asyncio
async def test_regex_wins_llm_only_fills_gaps():
    # Regex handles household_size; the LLM shouldn't override it even if
    # it returns a (wrong) value for that key.
    llm = _FakeLLM('{"household_size": 99, "patient_name": "Maria Lopez"}')
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("household of three; patient is Maria Lopez")],
        input_schema=[_field("household_size", "number"), _field("patient_name", "text")],
    )
    by_key = {s.key: s.value for s in out}
    assert by_key["household_size"] == 3  # from regex, not the LLM's 99
    assert by_key["patient_name"] == "Maria Lopez"


@pytest.mark.asyncio
async def test_no_gaps_means_llm_not_called():
    llm = _FakeLLM('{"household_size": 3}')
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("family of three")],
        input_schema=[_field("household_size", "number")],
    )
    assert llm.calls == []  # regex covered it — no LLM spend
    assert out[0].value == 3


@pytest.mark.asyncio
async def test_falls_back_to_regex_on_bad_json():
    llm = _FakeLLM("Sorry, I can't do that.")
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("the patient is Maria Lopez")],
        input_schema=[_field("patient_name", "text")],
    )
    assert llm.calls  # the gap triggered an attempt
    assert out == []  # unparseable → regex result (empty for free text)


@pytest.mark.asyncio
async def test_falls_back_to_regex_on_llm_error():
    llm = _FakeLLM(raises=True)
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("household of four, patient Maria Lopez")],
        input_schema=[_field("household_size", "number"), _field("patient_name", "text")],
    )
    # Regex value survives the LLM crash; the free-text gap is just unfilled.
    assert {s.key: s.value for s in out} == {"household_size": 4}


@pytest.mark.asyncio
async def test_never_invents_fields_outside_schema():
    llm = _FakeLLM('{"patient_name": "Maria Lopez", "ssn": "123-45-6789"}')
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("Maria Lopez")],
        input_schema=[_field("patient_name", "text")],
    )
    assert {s.key for s in out} == {"patient_name"}  # ssn dropped


@pytest.mark.asyncio
async def test_boolean_coercion():
    llm = _FakeLLM('{"has_insurance": "yes"}')
    out = await LLMExtractor(llm=llm).extract(
        history=[_msg("they do have insurance through work")],
        input_schema=[_field("has_insurance", "boolean")],
    )
    # boolean regex may or may not fire on a long msg; the LLM value must be a bool.
    val = {s.key: s.value for s in out}.get("has_insurance")
    assert val is True


@pytest.mark.asyncio
async def test_prompt_is_scrubbed_before_llm():
    class _Scrubber:
        def scrub(self, text: str) -> str:
            return text.replace("SECRET", "[REDACTED]")

    llm = _FakeLLM('{"patient_name": "Maria Lopez"}')
    await LLMExtractor(llm=llm, scrubber=_Scrubber()).extract(
        history=[_msg("codeword SECRET, patient Maria Lopez")],
        input_schema=[_field("patient_name", "text")],
    )
    assert llm.calls and "SECRET" not in llm.calls[0]
    assert "[REDACTED]" in llm.calls[0]
