"""Tests for GENERATE nodes — document production ACTION subtype.

Covers: document + provenance produced, prompt PII-scrubbed before the
LLM, exactly-once generation on resume (Non-Negotiable #3), and pause
when a required template input is missing.
"""

from __future__ import annotations

import pytest

from cen.core.engine import AsyncWorkflowEngine
from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    GenerateSpec,
    NodeMetadata,
    NodeType,
    WorkflowInput,
)


class _CallCountingLLM:
    """Fake LLM recording every prompt so tests assert exact-once + scrub."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        self.calls.append(prompt)
        return "Dear Sir or Madam, please reconsider the denial. Sincerely, CEN."

    async def is_available(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "counting_mock"


class _SsnScrubber:
    """Minimal scrubber that redacts a 9-digit SSN, so tests can assert
    the prompt was scrubbed before it reached the LLM."""

    def scrub(self, text: str) -> str:
        import re

        return re.sub(r"\d{3}-\d{2}-\d{4}", "[REDACTED_SSN]", text)


def _generate_aop() -> AOPDefinition:
    """Single generate node that drafts an appeal letter from context."""
    return AOPDefinition(
        module_name="generate_test",
        nodes=[
            AOPNode(
                id="draft_appeal",
                type=NodeType.ACTION,
                metadata=NodeMetadata(
                    label="Draft appeal letter",
                    action_kind="generate",
                    generate=GenerateSpec(
                        output_kind="appeal_letter",
                        prompt="Write an appeal for {patient_name} (SSN {ssn}).",
                        input_fields=["patient_name", "ssn"],
                        prompt_version="2.0",
                    ),
                ),
            ),
        ],
        edges=[],
    )


@pytest.mark.asyncio
async def test_generate_produces_document_with_provenance():
    llm = _CallCountingLLM()
    engine = AsyncWorkflowEngine(llm=llm)
    engine.load_aop(_generate_aop())

    result = await engine.execute(
        WorkflowInput(
            module_name="generate_test",
            context={"patient_name": "Maria Lopez", "ssn": "123-45-6789"},
        )
    )

    assert "draft_appeal_document" in result.context
    assert result.context["draft_appeal_document"].startswith("Dear Sir")
    prov = result.context["draft_appeal_provenance"]
    assert prov["model"] == "counting_mock"
    assert prov["prompt_version"] == "2.0"
    assert prov["output_kind"] == "appeal_letter"
    assert "timestamp" in prov


@pytest.mark.asyncio
async def test_generate_scrubs_prompt_before_llm():
    llm = _CallCountingLLM()
    engine = AsyncWorkflowEngine(llm=llm, scrubber=_SsnScrubber())
    engine.load_aop(_generate_aop())

    await engine.execute(
        WorkflowInput(
            module_name="generate_test",
            context={"patient_name": "Maria Lopez", "ssn": "123-45-6789"},
        )
    )

    assert len(llm.calls) == 1
    assert "123-45-6789" not in llm.calls[0]
    assert "[REDACTED_SSN]" in llm.calls[0]


@pytest.mark.asyncio
async def test_generate_is_idempotent_on_resume():
    llm = _CallCountingLLM()
    engine = AsyncWorkflowEngine(llm=llm)
    engine.load_aop(_generate_aop())

    ctx = {"patient_name": "Maria Lopez", "ssn": "123-45-6789"}
    first = await engine.execute(WorkflowInput(module_name="generate_test", context=ctx))
    # Resume: feed the returned context (carrying __node_outputs) back in.
    await engine.execute(
        WorkflowInput(module_name="generate_test", context=first.context)
    )

    assert len(llm.calls) == 1  # generated exactly once across both runs


@pytest.mark.asyncio
async def test_generate_pauses_when_input_missing():
    llm = _CallCountingLLM()
    engine = AsyncWorkflowEngine(llm=llm)
    engine.load_aop(_generate_aop())

    result = await engine.execute(
        WorkflowInput(module_name="generate_test", context={"patient_name": "Maria Lopez"})
    )

    assert result.pending_node == "draft_appeal"
    assert {f.key for f in (result.pending_input_fields or [])} == {"ssn"}
    assert len(llm.calls) == 0  # nothing generated while paused
