"""Bounded loop regions (LDCG) for AsyncWorkflowEngine.

A loop region is a strongly-connected block closed by a single
``loop_back`` edge (exit -> entry). The engine keeps its topological
walk for the DAG *skeleton* (the graph with loop_back edges removed) and
hands each region to ``run_loop_region``, which re-runs the region body
up to ``LoopSpec.max_iterations``, checks the exit condition after each
pass, and escalates to a human (``on_limit_next``) when the cap is hit
without exit.

v1 contract (validated at load, documented for authors):
- Exactly one region member — the *entry* — carries ``metadata.loop``.
- ``loop_back`` edge exit -> entry closes the region.
- The body contains no branching CONDITION nodes; the loop decision is
  made here by the controller via ``exit_condition_field``. This keeps
  us from evaluating ``nx.descendants`` over a cyclic graph.
- ``on_limit_next`` is an APPROVAL or HANDOFF node outside the region.

Idempotency: while inside a region the output cache is namespaced per
iteration (``ExecutionState.loop_suffix``), so each pass runs once and a
resumed case replays the current iteration instead of re-firing it
(Non-Negotiable #3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, FrozenSet, Optional

import networkx as nx

from cen.core.engine_helpers import collect_exclusive_branch
from cen.core.engine_runtime import (
    ExecutionState,
    StepResult,
    run_action_node,
    run_approval_node,
    run_condition_node,
    run_handoff_node,
)
from cen.core.exceptions import CycleDetectedError
from cen.core.models import AOPNode, LoopSpec, NodeType

if TYPE_CHECKING:
    from cen.core.engine import AsyncWorkflowEngine

_HANDLERS = {
    NodeType.ACTION: run_action_node,
    NodeType.CONDITION: run_condition_node,
    NodeType.HANDOFF: run_handoff_node,
    NodeType.APPROVAL: run_approval_node,
}


@dataclass
class LoopRegion:
    entry: str
    exit: str
    members: FrozenSet[str]
    spec: LoopSpec
    continue_next: Optional[str]  # exit's forward, non-loop-back, non-escalation successor


def _cyclic_sccs(graph: nx.DiGraph):
    """Yield each strongly-connected component that actually cycles
    (>1 member, or a single node with a self-loop)."""
    for scc in nx.strongly_connected_components(graph):
        if len(scc) > 1:
            yield scc
        else:
            only = next(iter(scc))
            if graph.has_edge(only, only):
                yield scc


def validate_loop_regions(graph: nx.DiGraph, nodes: Dict[str, AOPNode]) -> None:
    """Raise CycleDetectedError unless every cycle is a valid bounded
    region. Called from load_aop only when the graph is cyclic."""
    for scc in _cyclic_sccs(graph):
        members = set(scc)
        entries = [m for m in members if nodes[m].metadata.loop is not None]
        if len(entries) != 1:
            raise CycleDetectedError()  # unannotated or multi-entry cycle
        entry = entries[0]
        spec = nodes[entry].metadata.loop
        assert spec is not None
        if spec.exit_node not in members:
            raise CycleDetectedError()
        if not graph.has_edge(spec.exit_node, entry):
            raise CycleDetectedError()
        if graph.edges[spec.exit_node, entry].get("kind") != "loop_back":
            raise CycleDetectedError()
        if not spec.on_limit_next or spec.on_limit_next not in nodes:
            raise CycleDetectedError()
        # The escalation target must be a human gate (Non-Negotiable #1).
        if nodes[spec.on_limit_next].type not in (NodeType.APPROVAL, NodeType.HANDOFF):
            raise CycleDetectedError()


def detect_loop_regions(
    graph: nx.DiGraph, nodes: Dict[str, AOPNode]
) -> Dict[str, LoopRegion]:
    """Map entry-node-id -> LoopRegion for every valid bounded region.
    Returns {} for a pure DAG."""
    regions: Dict[str, LoopRegion] = {}
    for scc in _cyclic_sccs(graph):
        members = frozenset(scc)
        entries = [m for m in members if nodes[m].metadata.loop is not None]
        if len(entries) != 1:
            continue
        entry = entries[0]
        spec = nodes[entry].metadata.loop
        assert spec is not None
        continue_next: Optional[str] = None
        if spec.exit_node in graph:
            for target in graph.successors(spec.exit_node):
                if target not in members and target != spec.on_limit_next:
                    continue_next = target
                    break
        regions[entry] = LoopRegion(
            entry=entry,
            exit=spec.exit_node,
            members=members,
            spec=spec,
            continue_next=continue_next,
        )
    return regions


def _skeleton(graph: nx.DiGraph) -> nx.DiGraph:
    """The DAG that remains once loop_back edges are dropped."""
    skel = nx.DiGraph()
    skel.add_nodes_from(graph.nodes)
    for u, v, data in graph.edges(data=True):
        if data.get("kind") != "loop_back":
            skel.add_edge(u, v)
    return skel


def _eval_exit(spec: LoopSpec, context: Dict[str, Any]) -> bool:
    val = context.get(spec.exit_condition_field)
    if spec.exit_when == "==":
        return val == spec.exit_value
    if spec.exit_when == "!=":
        return val != spec.exit_value
    return bool(val)  # "truthy" (default)


def _apply_region_branch(
    skeleton: nx.DiGraph,
    keep: Optional[str],
    drop: Optional[str],
    state: ExecutionState,
) -> None:
    """After a region resolves or escalates, skip the branch not taken.
    Uses the acyclic skeleton so descendants are well-defined."""
    if drop and drop in skeleton:
        collect_exclusive_branch(skeleton, drop, keep or "", state.skip_set)


async def run_loop_region(
    engine: "AsyncWorkflowEngine",
    region: LoopRegion,
    state: ExecutionState,
    session_id: str | None,
    skeleton: nx.DiGraph,
) -> StepResult:
    """Run one bounded loop region: iterate the body until the exit
    condition is met (resolve) or the cap is hit (escalate)."""
    spec = region.spec
    loop_states: Dict[str, Any] = state.context.setdefault("__loop_state", {})
    ls = loop_states.setdefault(
        region.entry,
        {
            "iteration": 0,
            "status": "running",
            "exit_met": False,
            # Static region facts, surfaced so the UI can render "round N
            # of M" and a plain-language label without fetching the module.
            "max_iterations": spec.max_iterations,
            "label": engine.nodes[region.entry].metadata.label or region.entry,
        },
    )

    # Resume past an already-completed region: re-apply the branch it
    # took, never re-run the body (Non-Negotiable #3).
    if ls["status"] == "resolved":
        _apply_region_branch(skeleton, region.continue_next, spec.on_limit_next, state)
        return StepResult.CONTINUE
    if ls["status"] == "escalated":
        _apply_region_branch(skeleton, spec.on_limit_next, region.continue_next, state)
        return StepResult.CONTINUE

    body_order = list(nx.topological_sort(skeleton.subgraph(region.members)))

    while True:
        iteration = ls["iteration"]
        state.loop_suffix = f"#{iteration}"
        for nid in body_order:
            node = engine.nodes[nid]
            handler = _HANDLERS.get(node.type)
            if handler is None:
                continue
            result = await handler(engine, node, state, session_id)
            if result is StepResult.BREAK:
                # Paused mid-body (input/approval). Keep status running so
                # resume re-enters this same iteration and replays cache.
                state.loop_suffix = ""
                ls["status"] = "iterating"
                return StepResult.BREAK
        state.loop_suffix = ""

        exit_met = _eval_exit(spec, state.context)
        ls["iteration"] = iteration + 1
        ls["exit_met"] = exit_met

        if exit_met:
            ls["status"] = "resolved"
            _apply_region_branch(
                skeleton, region.continue_next, spec.on_limit_next, state
            )
            return StepResult.CONTINUE

        if ls["iteration"] >= spec.max_iterations:
            ls["status"] = "escalated"
            # Recorded via the audited node-event path (scrubbed, chained).
            await engine._emit_node_event(
                session_id,
                region.entry,
                "LOOP",
                f"escalated:iterations={ls['iteration']}",
                state.context,
            )
            _apply_region_branch(
                skeleton, spec.on_limit_next, region.continue_next, state
            )
            return StepResult.CONTINUE
        # else: loop again — the next iteration's cache suffix misses, so
        # the body re-executes. No skip_set to reset (bodies don't branch).


async def run_with_loops(
    engine: "AsyncWorkflowEngine",
    state: ExecutionState,
    session_id: str | None,
) -> None:
    """Walk the DAG skeleton; dispatch loop regions to the controller and
    every other node to its normal handler. Used only when the module
    has loop regions — pure DAGs take the unchanged fast path."""
    skeleton = _skeleton(engine.graph)
    regions = engine._loop_regions
    for node_id in nx.topological_sort(skeleton):
        if node_id in state.skip_set:
            continue
        if node_id in regions:
            result = await run_loop_region(
                engine, regions[node_id], state, session_id, skeleton
            )
            if result is StepResult.BREAK:
                break
            # Body already ran via the controller — skip its members so
            # the outer walk doesn't re-run them.
            state.skip_set |= regions[node_id].members
            continue
        node = engine.nodes[node_id]
        handler = _HANDLERS.get(node.type)
        if handler is None:
            continue
        result = await handler(engine, node, state, session_id)
        if result is StepResult.BREAK:
            break
