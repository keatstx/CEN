"""Guards the GENERATE wiring in insurance_appeal_assistant: draft_appeal
is a document-generation node, and an APPROVAL gate sits between it and
the send step (Non-Negotiable #1 — nothing consequential without human
sign-off)."""

from __future__ import annotations

from pathlib import Path

from cen.core.aop_parser import load_aop_from_file
from cen.core.engine import AsyncWorkflowEngine
from cen.core.models import NodeType

MODULES_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "cen" / "modules"


def _load():
    return load_aop_from_file(MODULES_DIR / "insurance_appeal_assistant.json")


def test_draft_appeal_is_a_generate_node():
    aop = _load()
    node = next(n for n in aop.nodes if n.id == "draft_appeal")
    assert node.type == NodeType.ACTION
    assert node.metadata.action_kind == "generate"
    assert node.metadata.generate is not None
    assert node.metadata.generate.output_kind == "appeal_letter"
    assert set(node.metadata.generate.input_fields) == {"patient_name", "denial_reason"}


def test_approval_gate_sits_before_send():
    aop = _load()
    nodes = {n.id: n for n in aop.nodes}
    edges = {(e.source, e.target) for e in aop.edges}
    # draft (generate) -> counselor_qa (APPROVAL) -> submit
    assert ("draft_appeal", "counselor_qa") in edges
    assert nodes["counselor_qa"].type == NodeType.APPROVAL
    assert ("counselor_qa", "submit_appeal") in edges


def test_debt_negotiation_is_a_bounded_loop():
    """negotiation_round is a real bounded loop region that escalates to a
    HANDOFF gate when the round cap is hit (Non-Negotiable #1)."""
    aop = load_aop_from_file(MODULES_DIR / "debt_cancellation_engine.json")
    engine = AsyncWorkflowEngine()
    engine.load_aop(aop)  # would raise if the cycle weren't a valid region
    assert "negotiation_round" in engine._loop_regions
    region = engine._loop_regions["negotiation_round"]
    assert region.spec.max_iterations == 3
    assert region.continue_next == "credit_bureau_dispute"
    nodes = {n.id: n for n in aop.nodes}
    assert nodes[region.spec.on_limit_next].type == NodeType.HANDOFF
