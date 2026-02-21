from __future__ import annotations

import operator
import time
from typing import Dict, Set

import networkx as nx

from core.models import (
    AOPDefinition,
    AOPNode,
    NodeType,
    TelemetryEvent,
    WorkflowInput,
    WorkflowResult,
)

OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


class WorkflowEngine:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes: dict[str, AOPNode] = {}
        self.module_name: str = ""

    def load_aop(self, aop: AOPDefinition) -> None:
        self.graph.clear()
        self.nodes.clear()
        self.module_name = aop.module_name

        for node in aop.nodes:
            self.graph.add_node(node.id, data=node)
            self.nodes[node.id] = node

        for edge in aop.edges:
            self.graph.add_edge(edge.source, edge.target, label=edge.label)

        if not nx.is_directed_acyclic_graph(self.graph):
            raise ValueError(
                "AOP contains a cycle — circular logic paths are not allowed."
            )

    def _evaluate_condition(self, node: AOPNode, context: dict) -> bool:
        field = node.condition_field
        op_str = node.condition_operator
        value = node.condition_value

        if field is None or op_str is None or value is None:
            return False

        actual = context.get(field)
        if actual is None:
            return False

        op_func = OPERATORS.get(op_str)
        if op_func is None:
            raise ValueError(f"Unknown operator: {op_str}")

        try:
            return op_func(float(actual), float(value))
        except (TypeError, ValueError):
            return op_func(actual, value)

    def execute(self, workflow_input: WorkflowInput) -> WorkflowResult:
        start = time.time()
        context = dict(workflow_input.context)
        executed: list[str] = []
        outcome = "completed"

        sorted_nodes = list(nx.topological_sort(self.graph))

        skip_set: set[str] = set()

        for node_id in sorted_nodes:
            if node_id in skip_set:
                continue

            node = self.nodes[node_id]

            if node.type == NodeType.ACTION:
                executed.append(node_id)
                context[f"{node_id}_status"] = "done"

            elif node.type == NodeType.CONDITION:
                executed.append(node_id)
                result = self._evaluate_condition(node, context)
                context[f"{node_id}_result"] = result

                # Determine which branch to skip
                if result:
                    if node.false_next:
                        self._collect_exclusive_branch(
                            node.false_next, node.true_next or "", skip_set
                        )
                else:
                    if node.true_next:
                        self._collect_exclusive_branch(
                            node.true_next, node.false_next or "", skip_set
                        )

            elif node.type == NodeType.HANDOFF:
                executed.append(node_id)
                outcome = f"handoff:{node.metadata.label or node_id}"

        elapsed = time.time() - start

        self._emit_telemetry(
            TelemetryEvent(
                module=self.module_name,
                outcome=outcome,
                latency=f"{elapsed:.2f}s",
                nodes_executed=len(executed),
            )
        )

        return WorkflowResult(
            module_name=self.module_name,
            executed_nodes=executed,
            final_outcome=outcome,
            context=context,
        )

    def _collect_exclusive_branch(
        self, skip_root: str, keep_root: str, skip_set: set[str]
    ) -> None:
        """Skip nodes reachable only from skip_root and not from keep_root."""
        if skip_root not in self.graph:
            return
        skip_candidates = {skip_root} | nx.descendants(self.graph, skip_root)
        keep_reachable = set()
        if keep_root and keep_root in self.graph:
            keep_reachable = {keep_root} | nx.descendants(self.graph, keep_root)
        for node in skip_candidates - keep_reachable:
            skip_set.add(node)

    def _emit_telemetry(self, event: TelemetryEvent) -> None:
        # Strips PII — only sends anonymous operational data
        print(
            f"[Telemetry] module={event.module} outcome={event.outcome} "
            f"latency={event.latency} nodes={event.nodes_executed}"
        )
