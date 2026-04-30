"""Tests for the SOP fix-proposal + apply engine.

The proposals are the contract — the inline-fix UI only works as well
as these heuristics. The Proforma fixture has 4 cycle errors by
design, so we use it to exercise the cycle path against real data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
    ProposedFix,
)
from cen.sop.extractor import RegexExtractor
from cen.sop.fixer import annotate_with_fixes, apply_fix, propose_fixes
from cen.sop.validators import validate_draft


PROFORMA = Path(__file__).parent / "fixtures" / "proforma.md"


def _node(
    node_id: str,
    type_: NodeType = NodeType.ACTION,
    *,
    true_next: str | None = None,
    false_next: str | None = None,
    label: str = "",
) -> AOPNode:
    return AOPNode(
        id=node_id,
        type=type_,
        metadata=NodeMetadata(label=label or node_id),
        condition_field=f"{node_id}__answer" if type_ == NodeType.CONDITION else None,
        condition_operator="equals" if type_ == NodeType.CONDITION else None,
        condition_value="yes" if type_ == NodeType.CONDITION else None,
        true_next=true_next,
        false_next=false_next,
    )


# ── Unknown branch target ───────────────────────────────────────────


def test_unknown_branch_target_proposes_closest_id():
    draft = AOPDefinition(
        module_name="m",
        nodes=[
            _node("a"),
            _node("c", NodeType.CONDITION, true_next="a", false_next="re_submit"),
            _node("re_submi"),  # close-enough id, edit distance 1
        ],
        edges=[],
    )
    issues = validate_draft(draft)
    target = next(i for i in issues if "re_submit" in i.message)
    fixes = propose_fixes(target, draft)
    assert any(f.kind == "rename_target" and f.payload["new_target"] == "re_submi" for f in fixes)
    # confidence boosted because edit distance is 1
    rename = next(f for f in fixes if f.kind == "rename_target")
    assert rename.confidence >= 0.8


def test_unknown_branch_target_also_offers_add_node_and_drop():
    draft = AOPDefinition(
        module_name="m",
        nodes=[
            _node("a"),
            _node("c", NodeType.CONDITION, true_next="a", false_next="missing"),
        ],
        edges=[],
    )
    issues = validate_draft(draft)
    target = next(i for i in issues if "missing" in i.message)
    kinds = {f.kind for f in propose_fixes(target, draft)}
    assert "add_node" in kinds
    assert "drop_edge" in kinds


def test_apply_rename_target_updates_branch():
    draft = AOPDefinition(
        module_name="m",
        nodes=[
            _node("a"),
            _node("c", NodeType.CONDITION, true_next="a", false_next="missing"),
            _node("b"),
        ],
        edges=[],
    )
    fix = ProposedFix(
        kind="rename_target",
        label="Rename to b",
        payload={"node_id": "c", "side": "false_next", "new_target": "b"},
    )
    new_draft = apply_fix(draft, fix)
    cond = next(n for n in new_draft.nodes if n.id == "c")
    assert cond.false_next == "b"


def test_apply_add_node_creates_node_and_wires_branch():
    draft = AOPDefinition(
        module_name="m",
        nodes=[
            _node("c", NodeType.CONDITION, true_next="a", false_next="ghost"),
            _node("a"),
        ],
        edges=[],
    )
    fix = ProposedFix(
        kind="add_node",
        label="Add ghost",
        payload={
            "node_id": "ghost",
            "type": "ACTION",
            "label": "Ghost",
            "wire_branch": {"node_id": "c", "side": "false_next"},
        },
    )
    new_draft = apply_fix(draft, fix)
    assert any(n.id == "ghost" for n in new_draft.nodes)
    cond = next(n for n in new_draft.nodes if n.id == "c")
    assert cond.false_next == "ghost"


def test_apply_drop_edge_clears_branch_side():
    draft = AOPDefinition(
        module_name="m",
        nodes=[
            _node("c", NodeType.CONDITION, true_next="a", false_next="ghost"),
            _node("a"),
        ],
        edges=[],
    )
    fix = ProposedFix(
        kind="drop_edge",
        label="Drop false branch",
        payload={"node_id": "c", "side": "false_next"},
    )
    new_draft = apply_fix(draft, fix)
    cond = next(n for n in new_draft.nodes if n.id == "c")
    assert cond.false_next is None


# ── Cycle ──────────────────────────────────────────────────────────


def test_cycle_proposes_drop_edge_to_break_loop():
    draft = AOPDefinition(
        module_name="m",
        nodes=[_node("a"), _node("b")],
        edges=[
            AOPEdge(source="a", target="b"),
            AOPEdge(source="b", target="a"),
        ],
    )
    issues = validate_draft(draft)
    cycle_issues = [i for i in issues if "cycle" in i.message.lower()]
    # At least one issue gets fix proposals.
    assert any(propose_fixes(i, draft) for i in cycle_issues)


def test_apply_drop_edge_breaks_cycle_for_real():
    draft = AOPDefinition(
        module_name="m",
        nodes=[_node("a"), _node("b")],
        edges=[
            AOPEdge(source="a", target="b"),
            AOPEdge(source="b", target="a"),
        ],
    )
    fix = ProposedFix(
        kind="drop_edge",
        label="break loop",
        payload={"edge_source": "b", "edge_target": "a"},
    )
    new_draft = apply_fix(draft, fix)
    new_issues = validate_draft(new_draft)
    assert not any("cycle" in i.message.lower() for i in new_issues if i.severity == "error")


# ── snake_case_id ──────────────────────────────────────────────────


def test_snake_case_id_proposes_rename():
    draft = AOPDefinition(
        module_name="m", nodes=[_node("MyNode-1")], edges=[]
    )
    issues = validate_draft(draft)
    snake = next(i for i in issues if "snake_case" in i.message)
    fixes = propose_fixes(snake, draft)
    assert fixes
    assert fixes[0].kind == "snake_case_id"
    assert fixes[0].payload["new_id"] == "mynode_1"
    assert fixes[0].confidence >= 0.9


def test_apply_rename_id_updates_all_references():
    draft = AOPDefinition(
        module_name="m",
        nodes=[
            _node("Bad-Id"),
            _node("c", NodeType.CONDITION, true_next="Bad-Id", false_next="b"),
            _node("b"),
        ],
        edges=[AOPEdge(source="Bad-Id", target="c")],
    )
    fix = ProposedFix(
        kind="snake_case_id",
        label="Rename",
        payload={"old_id": "Bad-Id", "new_id": "bad_id"},
    )
    new_draft = apply_fix(draft, fix)
    ids = {n.id for n in new_draft.nodes}
    assert "Bad-Id" not in ids
    assert "bad_id" in ids
    cond = next(n for n in new_draft.nodes if n.id == "c")
    assert cond.true_next == "bad_id"
    assert any(e.source == "bad_id" for e in new_draft.edges)


# ── Real-SOP integration ───────────────────────────────────────────


def test_proforma_real_sop_yields_fixes_for_every_cycle_error():
    """The Proforma fixture has 4 cycle errors. Every one should get
    at least one drop_edge proposal."""
    md = PROFORMA.read_text(encoding="utf-8")
    draft = RegexExtractor().extract(
        canonical_md=md, sop_id="proforma", suggested_module_name="m"
    )
    issues = annotate_with_fixes(validate_draft(draft), draft)
    cycle_errors = [
        i for i in issues
        if i.severity == "error" and "cycle" in i.message.lower()
    ]
    assert cycle_errors, "expected cycle errors on the Proforma fixture"
    # Every cycle issue gets at least one drop_edge fix.
    for issue in cycle_errors:
        kinds = {f.kind for f in issue.fixes}
        assert "drop_edge" in kinds, f"no fix for cycle on {issue.node_id}"


def test_proforma_auto_fix_loop_eventually_clears_cycles():
    """Iterative high-confidence apply should clear all cycle errors
    if the heuristics work end-to-end."""
    md = PROFORMA.read_text(encoding="utf-8")
    draft = RegexExtractor().extract(
        canonical_md=md, sop_id="proforma", suggested_module_name="m"
    )
    # Run the same loop the auto_fix endpoint runs but accept any
    # confidence since cycle fixes top out at 0.7. (In production the
    # endpoint requires 0.9 to avoid unwanted edits; for this test we
    # validate the engine *can* fix cycles given enough iterations.)
    for _ in range(20):
        issues = annotate_with_fixes(validate_draft(draft), draft)
        next_fix = None
        for issue in issues:
            if issue.severity != "error":
                continue
            if issue.fixes:
                next_fix = issue.fixes[0]
                break
        if next_fix is None:
            break
        draft = apply_fix(draft, next_fix)
    final = validate_draft(draft)
    cycle_errors = [
        i for i in final
        if i.severity == "error" and "cycle" in i.message.lower()
    ]
    assert not cycle_errors, "cycles should be resolvable by the fix engine"


# ── annotate_with_fixes shape ──────────────────────────────────────


def test_annotate_attaches_fixes_to_each_issue():
    draft = AOPDefinition(
        module_name="m",
        nodes=[_node("MyNode")],  # not snake_case → fixable
        edges=[],
    )
    issues = annotate_with_fixes(validate_draft(draft), draft)
    snake = next(i for i in issues if "snake_case" in i.message)
    assert len(snake.fixes) >= 1
    assert snake.fixes[0].kind == "snake_case_id"
