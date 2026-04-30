"""Fix proposals for validation issues on an SOP draft.

For each issue the validator surfaces, this module computes 1-3
``ProposedFix`` entries the user can apply with one tap. Pure
functions — no I/O, no LLM. The fixes themselves are applied by
``apply_fix()`` further down, which mutates a copy of the draft and
returns the updated module.

Coverage (issue message → fix kinds):

- "CONDITION branch points at unknown node 'X'"
    → rename_target (closest existing id by edit distance)
    → add_node (create an ACTION node with id X)
    → drop_edge (clear the offending branch)

- "CONDITION has only one branch wired"  (warning)
    → wire_branch (point unwired side at the next sequential node)

- "Node is unreachable"
    → wire_edge (add edge from the chronologically-prior node)
    → delete_node

- "Node id 'X' is not snake_case"
    → snake_case_id (rename to canonical form)

- "Node participates in a cycle"
    → drop_edge (per back-edge in the cycle, user picks)

- "CONDITION node has no branches wired"
    → wire_branch_pair (use the first two NEXT NODE(S) edges)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

import networkx as nx

from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
    ProposedFix,
    ValidationIssue,
)


# ── Public entry points ─────────────────────────────────────────────


def propose_fixes(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    """Return ranked fixes for a single validation issue.

    Empty list when no automatic fix is possible (the user has to edit
    manually). Ranked by confidence — caller surfaces them in order.
    """
    msg = issue.message.lower()
    if "branch points at unknown node" in msg:
        return _propose_unknown_branch_target(issue, draft)
    if "only one branch wired" in msg:
        return _propose_wire_missing_branch(issue, draft)
    if "is unreachable" in msg:
        return _propose_reach_unreachable(issue, draft)
    if "is not snake_case" in msg:
        return _propose_snake_case_id(issue, draft)
    if "participates in a cycle" in msg:
        return _propose_drop_cycle_edge(issue, draft)
    if "has no branches wired" in msg:
        return _propose_seed_branches(issue, draft)
    return []


def annotate_with_fixes(
    issues: List[ValidationIssue], draft: AOPDefinition
) -> List[ValidationIssue]:
    """Return a copy of ``issues`` with the ``fixes`` field populated."""
    return [
        issue.model_copy(update={"fixes": propose_fixes(issue, draft)})
        for issue in issues
    ]


def apply_fix(draft: AOPDefinition, fix: ProposedFix) -> AOPDefinition:
    """Return a new AOPDefinition with the fix applied.

    Raises ValueError when the payload is invalid for the given kind.
    The caller (the route layer) re-runs validate_draft on the result
    so the user sees the post-fix issue list.
    """
    if fix.kind == "rename_target":
        return _apply_rename_target(draft, fix.payload)
    if fix.kind == "add_node":
        return _apply_add_node(draft, fix.payload)
    if fix.kind == "drop_edge":
        return _apply_drop_edge(draft, fix.payload)
    if fix.kind == "rename_id" or fix.kind == "snake_case_id":
        return _apply_rename_id(draft, fix.payload)
    if fix.kind == "wire_branch":
        return _apply_wire_branch(draft, fix.payload)
    if fix.kind == "delete_node":
        return _apply_delete_node(draft, fix.payload)
    if fix.kind == "wire_branch_pair":
        return _apply_wire_branch_pair(draft, fix.payload)
    raise ValueError(f"Unknown fix kind: {fix.kind}")


# ── Proposal helpers ────────────────────────────────────────────────


def _propose_unknown_branch_target(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    if not issue.node_id:
        return []
    node = _find_node(draft, issue.node_id)
    if node is None:
        return []
    bad_target = _extract_quoted(issue.message)
    if not bad_target:
        return []
    side = _which_branch_points_at(node, bad_target)
    if side is None:
        return []

    fixes: List[ProposedFix] = []
    closest = _closest_id(bad_target, [n.id for n in draft.nodes if n.id != issue.node_id])
    if closest:
        fixes.append(
            ProposedFix(
                kind="rename_target",
                label=f"Point this branch at '{closest}' instead",
                payload={
                    "node_id": issue.node_id,
                    "side": side,
                    "new_target": closest,
                },
                confidence=0.85 if _edit_distance(bad_target, closest) <= 2 else 0.55,
            )
        )
    fixes.append(
        ProposedFix(
            kind="add_node",
            label=f"Add a new step called '{bad_target}'",
            payload={
                "node_id": bad_target,
                "type": "ACTION",
                "label": _humanize(bad_target),
                "wire_branch": {"node_id": issue.node_id, "side": side},
            },
            confidence=0.6,
        )
    )
    fixes.append(
        ProposedFix(
            kind="drop_edge",
            label=f"Drop the {side} branch (ends the workflow on this side)",
            payload={
                "node_id": issue.node_id,
                "side": side,
            },
            confidence=0.4,
        )
    )
    return fixes


def _propose_wire_missing_branch(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    if not issue.node_id:
        return []
    node = _find_node(draft, issue.node_id)
    if node is None:
        return []
    side = "true_next" if not node.true_next else "false_next" if not node.false_next else None
    if side is None:
        return []
    next_seq = _next_sequential_node(draft, issue.node_id)
    fixes: List[ProposedFix] = []
    if next_seq:
        fixes.append(
            ProposedFix(
                kind="wire_branch",
                label=f"Point the unwired branch at '{next_seq}'",
                payload={
                    "node_id": issue.node_id,
                    "side": side,
                    "new_target": next_seq,
                },
                confidence=0.7,
            )
        )
    return fixes


def _propose_reach_unreachable(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    if not issue.node_id:
        return []
    prev = _previous_sequential_node(draft, issue.node_id)
    fixes: List[ProposedFix] = []
    if prev:
        fixes.append(
            ProposedFix(
                kind="wire_branch",
                label=f"Wire from '{prev}' to this step",
                payload={
                    "node_id": prev,
                    "side": "next_edge",
                    "new_target": issue.node_id,
                },
                confidence=0.6,
            )
        )
    fixes.append(
        ProposedFix(
            kind="delete_node",
            label="Delete this step",
            payload={"node_id": issue.node_id},
            confidence=0.4,
        )
    )
    return fixes


def _propose_snake_case_id(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    if not issue.node_id:
        return []
    new_id = _snake_case(issue.node_id)
    if new_id == issue.node_id:
        return []
    return [
        ProposedFix(
            kind="snake_case_id",
            label=f"Rename to '{new_id}'",
            payload={"old_id": issue.node_id, "new_id": new_id},
            confidence=0.95,
        )
    ]


def _propose_drop_cycle_edge(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    """For each cycle the node belongs to, propose dropping a back-edge.

    Picks the back-edge whose source is the node mentioned in the
    issue. The user can re-run if a different break is preferred.
    """
    if not issue.node_id:
        return []
    g = _to_nx(draft)
    fixes: List[ProposedFix] = []
    seen: set[tuple[str, str]] = set()
    try:
        cycles = list(nx.simple_cycles(g))
    except Exception:  # noqa: BLE001
        return []
    for cycle in cycles:
        if issue.node_id not in cycle:
            continue
        # Walk the cycle; propose dropping each edge that originates
        # from the issue node (most likely the one the navigator
        # wants to remove). Cap at 2 proposals per issue.
        for i, src in enumerate(cycle):
            if src != issue.node_id:
                continue
            tgt = cycle[(i + 1) % len(cycle)]
            key = (src, tgt)
            if key in seen:
                continue
            seen.add(key)
            fixes.append(
                ProposedFix(
                    kind="drop_edge",
                    label=f"Drop the edge from '{src}' to '{tgt}' (breaks the loop)",
                    payload={
                        "edge_source": src,
                        "edge_target": tgt,
                    },
                    confidence=0.7,
                )
            )
            if len(fixes) >= 2:
                return fixes
    return fixes


def _propose_seed_branches(
    issue: ValidationIssue, draft: AOPDefinition
) -> List[ProposedFix]:
    if not issue.node_id:
        return []
    next_targets = [e.target for e in draft.edges if e.source == issue.node_id]
    if len(next_targets) >= 2:
        return [
            ProposedFix(
                kind="wire_branch_pair",
                label=f"Wire branches to '{next_targets[0]}' (yes) and '{next_targets[1]}' (no)",
                payload={
                    "node_id": issue.node_id,
                    "true_next": next_targets[0],
                    "false_next": next_targets[1],
                },
                confidence=0.65,
            )
        ]
    return []


# ── Apply implementations ───────────────────────────────────────────


def _apply_rename_target(
    draft: AOPDefinition, payload: dict
) -> AOPDefinition:
    nodes = _clone_nodes(draft)
    node = next((n for n in nodes if n.id == payload["node_id"]), None)
    if node is None:
        raise ValueError(f"node not found: {payload['node_id']}")
    side = payload["side"]
    new_target = payload["new_target"]
    if side == "true_next":
        node.true_next = new_target
    elif side == "false_next":
        node.false_next = new_target
    else:
        raise ValueError(f"unknown side: {side}")
    edges = _clone_edges(draft)
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


def _apply_add_node(draft: AOPDefinition, payload: dict) -> AOPDefinition:
    nodes = _clone_nodes(draft)
    node_type = NodeType(payload.get("type", "ACTION"))
    new_node = AOPNode(
        id=payload["node_id"],
        type=node_type,
        metadata=NodeMetadata(
            label=payload.get("label", _humanize(payload["node_id"])),
            description=payload.get("description", ""),
        ),
    )
    nodes.append(new_node)

    edges = _clone_edges(draft)
    wire = payload.get("wire_branch")
    if wire:
        target_node = next(
            (n for n in nodes if n.id == wire["node_id"]), None
        )
        if target_node and wire["side"] in ("true_next", "false_next"):
            setattr(target_node, wire["side"], new_node.id)
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


def _apply_drop_edge(draft: AOPDefinition, payload: dict) -> AOPDefinition:
    nodes = _clone_nodes(draft)
    edges = _clone_edges(draft)
    if "edge_source" in payload and "edge_target" in payload:
        edges = [
            e for e in edges
            if not (e.source == payload["edge_source"] and e.target == payload["edge_target"])
        ]
    if "node_id" in payload and "side" in payload:
        node = next((n for n in nodes if n.id == payload["node_id"]), None)
        if node:
            if payload["side"] == "true_next":
                node.true_next = None
            elif payload["side"] == "false_next":
                node.false_next = None
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


def _apply_rename_id(draft: AOPDefinition, payload: dict) -> AOPDefinition:
    old_id = payload["old_id"]
    new_id = payload["new_id"]
    nodes = _clone_nodes(draft)
    edges = _clone_edges(draft)
    for n in nodes:
        if n.id == old_id:
            n.id = new_id
        if n.true_next == old_id:
            n.true_next = new_id
        if n.false_next == old_id:
            n.false_next = new_id
        if n.branches:
            n.branches = {k: (new_id if v == old_id else v) for k, v in n.branches.items()}
    for e in edges:
        if e.source == old_id:
            e.source = new_id
        if e.target == old_id:
            e.target = new_id
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


def _apply_wire_branch(draft: AOPDefinition, payload: dict) -> AOPDefinition:
    nodes = _clone_nodes(draft)
    edges = _clone_edges(draft)
    side = payload["side"]
    new_target = payload["new_target"]
    if side == "next_edge":
        edges.append(AOPEdge(source=payload["node_id"], target=new_target))
    else:
        node = next((n for n in nodes if n.id == payload["node_id"]), None)
        if node:
            setattr(node, side, new_target)
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


def _apply_wire_branch_pair(
    draft: AOPDefinition, payload: dict
) -> AOPDefinition:
    nodes = _clone_nodes(draft)
    edges = _clone_edges(draft)
    node = next((n for n in nodes if n.id == payload["node_id"]), None)
    if node:
        node.true_next = payload["true_next"]
        node.false_next = payload["false_next"]
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


def _apply_delete_node(draft: AOPDefinition, payload: dict) -> AOPDefinition:
    target_id = payload["node_id"]
    nodes = [n for n in _clone_nodes(draft) if n.id != target_id]
    edges = [
        e for e in _clone_edges(draft)
        if e.source != target_id and e.target != target_id
    ]
    # Also clear any branch pointers at the deleted node.
    for n in nodes:
        if n.true_next == target_id:
            n.true_next = None
        if n.false_next == target_id:
            n.false_next = None
        if n.branches:
            n.branches = {k: v for k, v in n.branches.items() if v != target_id}
    return draft.model_copy(update={"nodes": nodes, "edges": edges})


# ── Misc helpers ────────────────────────────────────────────────────


def _find_node(draft: AOPDefinition, node_id: str) -> Optional[AOPNode]:
    return next((n for n in draft.nodes if n.id == node_id), None)


def _which_branch_points_at(node: AOPNode, target: str) -> Optional[str]:
    if node.true_next == target:
        return "true_next"
    if node.false_next == target:
        return "false_next"
    return None


def _extract_quoted(text: str) -> Optional[str]:
    """Pull the first single-quoted token out of a validation message."""
    m = re.search(r"'([^']+)'", text)
    return m.group(1) if m else None


def _closest_id(target: str, candidates: List[str]) -> Optional[str]:
    """Return the candidate with the smallest edit distance to ``target``,
    or None when nothing's a sensible match (distance > 60% of length)."""
    if not candidates:
        return None
    scored = [(c, _edit_distance(target, c)) for c in candidates]
    best, distance = min(scored, key=lambda x: x[1])
    if distance > max(2, int(len(target) * 0.6)):
        return None
    return best


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein distance — small enough for the SOP id list (dozens)."""
    if a == b:
        return 0
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return max(m, n)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[n]


def _snake_case(s: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", s)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_").lower()
    return cleaned or "node"


def _humanize(s: str) -> str:
    return s.replace("_", " ").replace("-", " ").strip().title() or s


def _next_sequential_node(
    draft: AOPDefinition, node_id: str
) -> Optional[str]:
    """Return the id of the next node listed in document order, or None."""
    ids = [n.id for n in draft.nodes]
    try:
        idx = ids.index(node_id)
    except ValueError:
        return None
    return ids[idx + 1] if idx + 1 < len(ids) else None


def _previous_sequential_node(
    draft: AOPDefinition, node_id: str
) -> Optional[str]:
    ids = [n.id for n in draft.nodes]
    try:
        idx = ids.index(node_id)
    except ValueError:
        return None
    return ids[idx - 1] if idx > 0 else None


def _to_nx(draft: AOPDefinition) -> nx.DiGraph:
    g = nx.DiGraph()
    for n in draft.nodes:
        g.add_node(n.id)
    for e in draft.edges:
        if e.source in g and e.target in g:
            g.add_edge(e.source, e.target)
    # Branch pointers also count as edges for cycle detection.
    for n in draft.nodes:
        if n.true_next and n.true_next in g:
            g.add_edge(n.id, n.true_next)
        if n.false_next and n.false_next in g:
            g.add_edge(n.id, n.false_next)
    return g


def _clone_nodes(draft: AOPDefinition) -> List[AOPNode]:
    return [n.model_copy(deep=True) for n in draft.nodes]


def _clone_edges(draft: AOPDefinition) -> List[AOPEdge]:
    return [e.model_copy(deep=True) for e in draft.edges]
