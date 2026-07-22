"""Backward-compatibility tests for the expansion schema fields.

The new NodeMetadata / AOPEdge / spec fields must be additive: module
JSON authored before they existed has to load unchanged, and the new
fields must default to null/absent so no existing workflow changes
behavior.
"""

from __future__ import annotations

from cen.core.models import (
    AgenticTaskSpec,
    AOPDefinition,
    GenerateSpec,
    LoopSpec,
    NodeMetadata,
)


def test_legacy_module_json_loads_unchanged():
    """A node dict with none of the new fields loads with null defaults."""
    aop = AOPDefinition(
        module_name="legacy",
        nodes=[{"id": "a", "type": "ACTION", "metadata": {"label": "Old step"}}],
        edges=[{"source": "a", "target": "a2"}],
    )
    meta = aop.nodes[0].metadata
    assert meta.action_kind is None
    assert meta.generate is None
    assert meta.loop is None
    assert meta.tags is None
    assert meta.faq_pin is None
    assert meta.presentation_ref is None
    assert meta.tasks is None
    # Edge defaults to a normal forward edge.
    assert aop.edges[0].kind == "dag"


def test_new_fields_round_trip_through_definition():
    aop = AOPDefinition(
        module_name="expanded",
        nodes=[
            {
                "id": "gen",
                "type": "ACTION",
                "metadata": {
                    "action_kind": "generate",
                    "generate": {
                        "output_kind": "dispute_letter",
                        "prompt": "Dispute {bill_id}",
                        "input_fields": ["bill_id"],
                    },
                    "tags": ["function:drafting", "domain:debt"],
                    "faq_pin": ["faq-1", "faq-2"],
                    "presentation_ref": "artifact-123",
                },
            },
            {
                "id": "loop_entry",
                "type": "ACTION",
                "metadata": {
                    "loop": {
                        "exit_node": "loop_check",
                        "exit_condition_field": "settled",
                        "max_iterations": 4,
                        "on_limit_next": "escalate",
                    }
                },
            },
        ],
        edges=[{"source": "loop_check", "target": "loop_entry", "kind": "loop_back"}],
    )
    gen_meta = aop.nodes[0].metadata
    assert isinstance(gen_meta.generate, GenerateSpec)
    assert gen_meta.generate.output_kind == "dispute_letter"
    assert gen_meta.tags == ["function:drafting", "domain:debt"]
    assert gen_meta.faq_pin == ["faq-1", "faq-2"]
    assert gen_meta.presentation_ref == "artifact-123"

    loop_meta = aop.nodes[1].metadata
    assert isinstance(loop_meta.loop, LoopSpec)
    assert loop_meta.loop.max_iterations == 4
    assert aop.edges[0].kind == "loop_back"


def test_agentic_task_spec_defaults():
    spec = AgenticTaskSpec(name="file_followup")
    assert spec.trigger == "manual"
    assert spec.side_effecting is True
    assert spec.input_schema == []
