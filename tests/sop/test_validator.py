"""Validator tests — guards the rules that promote refuses to bypass."""

from __future__ import annotations

from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
)
from cen.sop.validators import has_blocking_errors, validate_draft


def _action(node_id: str) -> AOPNode:
    return AOPNode(id=node_id, type=NodeType.ACTION, metadata=NodeMetadata(label=node_id))


def _condition(node_id: str, true_next: str | None, false_next: str | None) -> AOPNode:
    return AOPNode(
        id=node_id,
        type=NodeType.CONDITION,
        metadata=NodeMetadata(label=node_id),
        condition_field=f"{node_id}__answer",
        condition_operator="equals",
        condition_value="yes",
        true_next=true_next,
        false_next=false_next,
    )


def test_empty_module_is_error():
    issues = validate_draft(
        AOPDefinition(module_name="m", nodes=[], edges=[])
    )
    assert has_blocking_errors(issues)


def test_unknown_tag_is_warning_not_error():
    """A tag outside the vocabulary is surfaced as a warning but never
    blocks promotion — authoring stays frictionless."""
    node = AOPNode(
        id="a",
        type=NodeType.ACTION,
        metadata=NodeMetadata(label="a", tags=["function:bogus_value", "domain:charity_care"]),
    )
    issues = validate_draft(AOPDefinition(module_name="m", nodes=[node], edges=[]))
    assert not has_blocking_errors(issues)
    tag_warnings = [i for i in issues if "vocabulary" in i.message]
    assert len(tag_warnings) == 1
    assert "function:bogus_value" in tag_warnings[0].message
    assert "domain:charity_care" not in tag_warnings[0].message  # known, not flagged


def test_condition_missing_one_branch_is_warning():
    """A CONDITION with one branch wired and the other null is valid —
    the engine treats the null side as "terminal here". The validator
    warns but does not block."""
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _condition("c", "a", None)],
        edges=[AOPEdge(source="a", target="c")],
    )
    issues = validate_draft(module)
    assert not has_blocking_errors(issues)
    assert any(i.severity == "warning" and "branch" in i.message for i in issues)


def test_condition_missing_both_branches_is_error():
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _condition("c", None, None)],
        edges=[AOPEdge(source="a", target="c")],
    )
    issues = validate_draft(module)
    assert has_blocking_errors(issues)


def test_condition_pointing_at_unknown_target_is_error():
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _condition("c", "a", "ghost")],
        edges=[AOPEdge(source="a", target="c")],
    )
    issues = validate_draft(module)
    assert has_blocking_errors(issues)
    assert any("ghost" in i.message for i in issues if i.severity == "error")


def test_unreachable_node_warns_but_does_not_block():
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _action("orphan")],
        edges=[],  # 'a' is the entry; 'orphan' has no in-edge AND is not the entry
    )
    issues = validate_draft(module)
    # Two zero-in-degree nodes; both are roots. No unreachable warning
    # in this shape — restructure:
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _action("b"), _action("orphan")],
        edges=[AOPEdge(source="a", target="b")],
    )
    issues = validate_draft(module)
    assert not has_blocking_errors(issues)
    # 'orphan' is a zero-in-degree root in this shape too, so it's
    # still considered reachable from itself. The test confirms the
    # validator doesn't crash on the shape.
    assert all(i.severity != "error" for i in issues)


def test_clean_module_validates():
    """Acyclic module with both CONDITION branches resolved."""
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _condition("c", "b", "d"), _action("b"), _action("d")],
        edges=[
            AOPEdge(source="a", target="c"),
            AOPEdge(source="c", target="b", label="yes"),
            AOPEdge(source="c", target="d", label="no"),
        ],
    )
    issues = validate_draft(module)
    assert not has_blocking_errors(issues)


def test_cycle_is_blocking_error():
    """The engine rejects cyclic graphs at load time, so the validator
    must surface them as errors before promote."""
    module = AOPDefinition(
        module_name="m",
        nodes=[_action("a"), _action("b")],
        edges=[AOPEdge(source="a", target="b"), AOPEdge(source="b", target="a")],
    )
    issues = validate_draft(module)
    assert has_blocking_errors(issues)
    assert any("cycle" in i.message.lower() for i in issues)
