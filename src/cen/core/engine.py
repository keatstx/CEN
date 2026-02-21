"""AsyncWorkflowEngine — executes AOP/DAG workflows with DI for LLM + EventBus."""

from __future__ import annotations

import operator
import time
from typing import TYPE_CHECKING, Any

import networkx as nx

from cen.core.exceptions import CycleDetectedError
from cen.core.models import (
    AOPDefinition,
    AOPNode,
    NodeType,
    WorkflowInput,
    WorkflowResult,
)

if TYPE_CHECKING:
    from cen.llm.base import LanguageModel
    from cen.telemetry.bus import AsyncEventBus

OPERATORS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


class AsyncWorkflowEngine:
    def __init__(
        self,
        llm: LanguageModel | None = None,
        event_bus: AsyncEventBus | None = None,
    ):
        self.graph = nx.DiGraph()
        self.nodes: dict[str, AOPNode] = {}
        self.module_name: str = ""
        self._llm = llm
        self._event_bus = event_bus

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
            raise CycleDetectedError()

    def _evaluate_condition(self, node: AOPNode, context: dict[str, Any]) -> bool:
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

    async def execute(self, workflow_input: WorkflowInput) -> WorkflowResult:
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
                # If the node has an llm_prompt param and we have an LLM, call it
                llm_prompt = node.metadata.params.get("llm_prompt")
                if llm_prompt and self._llm:
                    prompt = llm_prompt.format(**context) if "{" in llm_prompt else llm_prompt
                    llm_response = await self._llm.generate(prompt)
                    context[f"{node_id}_llm_response"] = llm_response
                context[f"{node_id}_status"] = "done"

            elif node.type == NodeType.CONDITION:
                executed.append(node_id)
                result = self._evaluate_condition(node, context)
                context[f"{node_id}_result"] = result

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

        if self._event_bus:
            from cen.telemetry.events import WorkflowCompletedEvent

            await self._event_bus.emit(
                WorkflowCompletedEvent(
                    module=self.module_name,
                    outcome=outcome,
                    latency=elapsed,
                    nodes_executed=len(executed),
                    context=context,
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
        keep_reachable: set[str] = set()
        if keep_root and keep_root in self.graph:
            keep_reachable = {keep_root} | nx.descendants(self.graph, keep_root)
        for node in skip_candidates - keep_reachable:
            skip_set.add(node)
