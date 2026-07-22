"""Validation rules for a draft AOPDefinition.

Run after extraction; surface issues to the author in the review UI.
The promoter refuses to write a module file when any error-severity
issue is present.
"""

from __future__ import annotations

from collections import deque
from typing import List

from cen.core.models import AOPDefinition, NodeType, ValidationIssue
from cen.core.tags import unknown_tags


def validate_draft(module: AOPDefinition) -> List[ValidationIssue]:
    issues: list[ValidationIssue] = []
    node_ids = {n.id for n in module.nodes}

    if not module.nodes:
        issues.append(ValidationIssue(severity="error", message="Module has no nodes."))
        return issues

    # ── Node-level checks ─────────────────────────────────────────
    for node in module.nodes:
        if not node.id:
            issues.append(
                ValidationIssue(severity="error", message="Node has empty id.")
            )
            continue
        # Tags outside the project vocabulary — a warning, never a
        # blocker. Keeps authoring frictionless while surfacing drift.
        if node.metadata.tags:
            bad = unknown_tags(node.metadata.tags)
            if bad:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        node_id=node.id,
                        message=(
                            "Tag(s) not in the project vocabulary: "
                            + ", ".join(bad)
                            + ". Allowed, but check for typos."
                        ),
                    )
                )
        if node.id != node.id.lower() or " " in node.id:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    node_id=node.id,
                    message=f"Node id '{node.id}' is not snake_case.",
                )
            )
        if node.type == NodeType.CONDITION:
            both_missing = not node.true_next and not node.false_next
            one_missing = bool(node.true_next) ^ bool(node.false_next)
            if both_missing:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        node_id=node.id,
                        message="CONDITION node has no branches wired.",
                    )
                )
            elif one_missing:
                # Engine treats a null branch as "terminal on that side" —
                # a draft with one branch wired up is partially complete,
                # not broken. Author should fix in review.
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        node_id=node.id,
                        message="CONDITION has only one branch wired; the other side will end the workflow.",
                    )
                )
            for branch_target in [node.true_next, node.false_next]:
                if branch_target and branch_target not in node_ids:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node_id=node.id,
                            message=f"CONDITION branch points at unknown node '{branch_target}'.",
                        )
                    )

    # ── Edge integrity ────────────────────────────────────────────
    out_edges: dict[str, list[str]] = {n.id: [] for n in module.nodes}
    for edge in module.edges:
        if edge.source not in node_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Edge from unknown node '{edge.source}' to '{edge.target}'.",
                )
            )
            continue
        if edge.target not in node_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    node_id=edge.source,
                    message=f"Edge points at unknown node '{edge.target}'.",
                )
            )
            continue
        out_edges[edge.source].append(edge.target)

    # ── Reachability ──────────────────────────────────────────────
    in_degree: dict[str, int] = {n.id: 0 for n in module.nodes}
    for edge in module.edges:
        if edge.target in in_degree:
            in_degree[edge.target] += 1
    roots = [nid for nid, deg in in_degree.items() if deg == 0]
    if not roots and module.nodes:
        issues.append(
            ValidationIssue(
                severity="warning",
                message="Module has no entry node (every node is referenced); engine will start at first node.",
            )
        )
        roots = [module.nodes[0].id]

    reachable: set[str] = set()
    queue: deque[str] = deque(roots)
    while queue:
        nid = queue.popleft()
        if nid in reachable:
            continue
        reachable.add(nid)
        for tgt in out_edges.get(nid, []):
            queue.append(tgt)
    for n in module.nodes:
        if n.id not in reachable:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    node_id=n.id,
                    message="Node is unreachable from the entry node.",
                )
            )

    # ── Terminal-node sanity ──────────────────────────────────────
    for n in module.nodes:
        if n.type == NodeType.CONDITION:
            continue
        if not out_edges.get(n.id) and not (
            n.id == module.nodes[-1].id  # last node may legitimately be terminal
        ):
            issues.append(
                ValidationIssue(
                    severity="info",
                    node_id=n.id,
                    message="Non-terminal node has no outgoing edge.",
                )
            )

    # ── Cycle detection ──────────────────────────────────────────
    # The current engine rejects cyclic graphs at load time. Many SOPs
    # have legitimate revision loops ("if NO, refine and resubmit"); we
    # mark these as errors so the author can break the loop in review
    # before promote. When the engine eventually supports loops natively
    # this becomes a warning.
    for cycle_node in _find_cycle_nodes(out_edges):
        issues.append(
            ValidationIssue(
                severity="error",
                node_id=cycle_node,
                message="Node participates in a cycle; the engine rejects cyclic graphs.",
            )
        )

    return issues


def _find_cycle_nodes(out_edges: dict[str, list[str]]) -> list[str]:
    """Return node ids that are part of any directed cycle."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in out_edges}
    cycle_members: set[str] = set()
    stack: list[tuple[str, int]] = []  # (node, child_index)

    for start in out_edges:
        if color[start] != WHITE:
            continue
        stack.append((start, 0))
        path: list[str] = []
        on_path: set[str] = set()
        color[start] = GRAY
        path.append(start)
        on_path.add(start)
        while stack:
            node, idx = stack[-1]
            children = out_edges.get(node, [])
            if idx >= len(children):
                color[node] = BLACK
                stack.pop()
                if path and path[-1] == node:
                    path.pop()
                    on_path.discard(node)
                continue
            stack[-1] = (node, idx + 1)
            child = children[idx]
            if child not in color:
                continue
            if color[child] == WHITE:
                color[child] = GRAY
                path.append(child)
                on_path.add(child)
                stack.append((child, 0))
            elif color[child] == GRAY:
                # Found a back-edge — every node from `child` to the
                # top of `path` is on the cycle.
                in_cycle = False
                for nid in path:
                    if nid == child:
                        in_cycle = True
                    if in_cycle:
                        cycle_members.add(nid)
    return sorted(cycle_members)


def has_blocking_errors(issues: List[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)
