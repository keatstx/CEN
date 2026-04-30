"""Pure helper functions extracted from the engine to keep
``engine.py`` under the 300-line bar (CLAUDE.md §4.9).

Everything here is stateless or takes its state explicitly so the main
``AsyncWorkflowEngine`` stays focused on the execution loop. The
helpers cover three concerns:

1. Condition evaluation — comparing context values against a node's
   declared operator + value.
2. Input prompt derivation — building the ``InputField`` the engine
   surfaces when a step pauses for user input.
3. Branch skipping — figuring out which downstream nodes a CONDITION
   should mark unreachable on a given branch decision.

Tests for these live in ``tests/core/test_engine.py`` (covered by the
existing engine test suite — these are extractions, not behavior
changes).
"""

from __future__ import annotations

import operator
from typing import Any, Iterable

import networkx as nx

from cen.core.models import AOPNode, InputField, NodeType


# ── Constants ────────────────────────────────────────────────────────


OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
}

NUMERIC_OPS = {"<", "<=", ">", ">="}


def humanize(s: str) -> str:
    """Turn 'approved_full' into 'Approved Full' for select labels."""
    return s.replace("_", " ").strip().title() if s else s


# ── Condition evaluation ────────────────────────────────────────────


def evaluate_condition(node: AOPNode, context: dict[str, Any]) -> bool:
    """Return True/False for a CONDITION node against the live context.

    Defensive: returns False (rather than raising) on type mismatches
    or missing fields so a malformed input doesn't 500 the request.
    """
    field = node.condition_field
    op_str = node.condition_operator
    value = node.condition_value

    if field is None or op_str is None:
        return False

    if node.condition_value_field is not None:
        value = context.get(node.condition_value_field)

    if value is None:
        return False

    actual = context.get(field)
    if actual is None:
        return False

    op_func = OPERATORS.get(op_str)
    if op_func is None:
        raise ValueError(f"Unknown operator: {op_str}")

    if op_str in NUMERIC_OPS:
        try:
            return op_func(float(actual), float(value))
        except (TypeError, ValueError):
            return False
    try:
        return op_func(actual, value)
    except TypeError:
        return False


# ── Input prompt derivation ─────────────────────────────────────────


def missing_required_inputs(
    node: AOPNode, context: dict[str, Any]
) -> list[InputField] | None:
    """Return the subset of an ACTION node's input_schema whose required
    fields are missing from context. Returns None if nothing is missing
    or there is no schema declared.
    """
    schema = node.metadata.input_schema
    if not schema:
        return None
    missing = [f for f in schema if f.required and context.get(f.key) is None]
    return missing or None


def auto_derive_condition_input(
    node: AOPNode,
    context: dict[str, Any],
    *,
    aggregated_values: list[str] | None = None,
) -> InputField | None:
    """Auto-derive an input prompt for a CONDITION node when its
    ``condition_field`` is missing from context. The field type is
    inferred from operator + value; multi-choice CONDITIONs use the
    pre-aggregated list passed in via ``aggregated_values`` so siblings
    that test the same field share an option set.

    Returns None when the field is already present (engine proceeds
    normally) or the node has no ``condition_field`` at all.
    """
    field = node.condition_field
    if not field:
        return None
    if context.get(field) is not None:
        return None

    op = node.condition_operator
    value = node.condition_value

    field_type = "text"
    options: list[dict[str, str]] | None = None

    if op == "switch" and node.branches:
        field_type = "select"
        options = [
            {"value": str(k), "label": humanize(str(k))}
            for k in node.branches.keys()
        ]
    elif op in NUMERIC_OPS:
        field_type = "number"
    elif op in ("in", "not in") and isinstance(value, (list, tuple)):
        field_type = "select"
        options = [
            {"value": str(v), "label": humanize(str(v))} for v in value
        ]
    elif isinstance(value, bool):
        field_type = "boolean"
    elif op in ("==", "!="):
        agg = aggregated_values or []
        if len(agg) >= 2:
            field_type = "select"
            options = [
                {"value": str(v), "label": humanize(str(v))} for v in agg
            ]
        elif len(agg) == 1:
            only = agg[0]
            field_type = "select"
            options = [
                {"value": str(only), "label": humanize(str(only))},
                {"value": "__other__", "label": "Something else"},
            ]

    label = node.metadata.label or f"Please provide {field.replace('_', ' ')}"
    description = node.metadata.description or ""
    return InputField(
        key=field,
        label=label,
        type=field_type,
        required=True,
        options=options,
        description=description,
    )


def collect_field_values_for_field(
    field: str, nodes: Iterable[AOPNode]
) -> list[str]:
    """Walk every CONDITION node in the DAG and return every distinct
    value tested against ``field``, in document order. Used to
    aggregate option lists for auto-derived multi-choice inputs.
    """
    seen: list[str] = []
    for n in nodes:
        if n.type != NodeType.CONDITION:
            continue
        if n.condition_field != field:
            continue
        if n.condition_operator in ("in", "not in") and isinstance(
            n.condition_value, (list, tuple)
        ):
            for v in n.condition_value:
                s = str(v)
                if s not in seen:
                    seen.append(s)
        elif n.condition_operator == "switch" and n.branches:
            for k in n.branches.keys():
                s = str(k)
                if s not in seen:
                    seen.append(s)
        elif n.condition_value is not None and not isinstance(
            n.condition_value, bool
        ):
            s = str(n.condition_value)
            if s not in seen:
                seen.append(s)
    return seen


# ── Branch skipping ─────────────────────────────────────────────────


def collect_exclusive_branch(
    graph: nx.DiGraph,
    skip_root: str,
    keep_root: str,
    skip_set: set[str],
) -> None:
    """Mutate ``skip_set`` in place — add every node reachable from
    ``skip_root`` that's not also reachable from ``keep_root``.

    Used by CONDITION node execution to prune the unselected branch
    from the topological traversal.
    """
    if skip_root not in graph:
        return
    skip_candidates = {skip_root} | nx.descendants(graph, skip_root)
    keep_reachable: set[str] = set()
    if keep_root and keep_root in graph:
        keep_reachable = {keep_root} | nx.descendants(graph, keep_root)
    for node in skip_candidates - keep_reachable:
        skip_set.add(node)
