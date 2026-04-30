"""AsyncWorkflowEngine — executes AOP/DAG workflows with DI for LLM + EventBus.

The class here is intentionally thin: it loads the AOP into a graph,
walks the topological sort, and dispatches each node to a per-type
handler in ``engine_runtime``. Pure helpers (condition evaluation,
input derivation, branch skipping) live in ``engine_helpers``. This
split keeps every file under the §4.9 size bar.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Awaitable

import networkx as nx

from cen.core.engine_helpers import (
    auto_derive_condition_input,
    collect_exclusive_branch,
    collect_field_values_for_field,
    evaluate_condition,
    missing_required_inputs,
)
from cen.core.engine_runtime import (
    ExecutionState,
    StepResult,
    run_action_node,
    run_approval_node,
    run_condition_node,
    run_handoff_node,
)
from cen.core.exceptions import CycleDetectedError
from cen.core.models import (
    AOPDefinition,
    AOPNode,
    InputField,
    NodeType,
    WorkflowInput,
    WorkflowResult,
)

if TYPE_CHECKING:
    from cen.llm.base import LanguageModel
    from cen.telemetry.bus import AsyncEventBus


# Per-node-type dispatch table — each handler shares the
# ExecutionState and reports back via StepResult. We use plain Any for
# the engine arg in the type alias because the class isn't defined yet
# at this point in the module (and the alias is evaluated immediately
# under Python 3.9).
_HandlerSig = Callable[..., Awaitable[StepResult]]
_DISPATCH: dict[NodeType, _HandlerSig] = {
    NodeType.ACTION: run_action_node,
    NodeType.CONDITION: run_condition_node,
    NodeType.HANDOFF: run_handoff_node,
    NodeType.APPROVAL: run_approval_node,
}


class AsyncWorkflowEngine:
    def __init__(
        self,
        llm: "LanguageModel | None" = None,
        event_bus: "AsyncEventBus | None" = None,
        llm_semaphore: asyncio.Semaphore | None = None,
    ):
        self.graph = nx.DiGraph()
        self.nodes: dict[str, AOPNode] = {}
        self.module_name: str = ""
        self._llm = llm
        self._event_bus = event_bus
        self._llm_semaphore = llm_semaphore

    def load_aop(self, aop: AOPDefinition) -> None:
        self.graph.clear()
        self.nodes.clear()
        self._aop = aop
        self.module_name = aop.module_name

        for node in aop.nodes:
            self.graph.add_node(node.id, data=node)
            self.nodes[node.id] = node

        for edge in aop.edges:
            self.graph.add_edge(edge.source, edge.target, label=edge.label)

        if not nx.is_directed_acyclic_graph(self.graph):
            raise CycleDetectedError()

    async def execute(
        self,
        workflow_input: WorkflowInput,
        approved_nodes: set[str] | None = None,
        session_id: str | None = None,
    ) -> WorkflowResult:
        """Run the workflow against the supplied context.

        Per-node-type handlers live in ``engine_runtime``; this method is
        a thin dispatcher that walks the topological sort and routes
        each node to the right handler.
        """
        start = time.time()
        context = dict(workflow_input.context)

        # Idempotency cache (Non-Negotiable #3): per-node outputs from
        # prior runs. Any cached node replays instead of re-executing,
        # so LLM calls and external side effects fire exactly once
        # across the lifetime of a case.
        node_outputs: dict[str, dict[str, Any]] = dict(
            context.get("__node_outputs", {})
        )

        state = ExecutionState(
            context=context,
            node_outputs=node_outputs,
            approved_nodes=approved_nodes or set(),
        )

        for node_id in nx.topological_sort(self.graph):
            if node_id in state.skip_set:
                continue
            node = self.nodes[node_id]

            handler = _DISPATCH.get(node.type)
            if handler is None:
                continue
            result = await handler(self, node, state, session_id)
            if result is StepResult.BREAK:
                break

        # Persist the per-node output cache back into context so the
        # session_store round-trips it on save/resume.
        state.context["__node_outputs"] = state.node_outputs

        elapsed = time.time() - start
        if self._event_bus:
            from cen.telemetry.events import WorkflowCompletedEvent

            await self._event_bus.emit(
                WorkflowCompletedEvent(
                    module=self.module_name,
                    outcome=state.outcome,
                    latency=elapsed,
                    nodes_executed=len(state.executed),
                    context=state.context,
                )
            )

        return WorkflowResult(
            module_name=self.module_name,
            executed_nodes=state.executed,
            final_outcome=state.outcome,
            context=state.context,
            pending_node=state.pending_input_node,
            pending_input_fields=state.pending_input_fields,
        )

    # ── Helper wrappers (delegate to engine_helpers) ────────────────
    # These thin wrappers exist because the runtime handlers call them
    # as methods on the engine (engine._missing_required_inputs etc.).
    # Keeping them here means tests and external callers that go
    # through ``self.<method>`` keep working.

    def _evaluate_condition(self, node: AOPNode, context: dict[str, Any]) -> bool:
        return evaluate_condition(node, context)

    @staticmethod
    def _missing_required_inputs(
        node: AOPNode, context: dict[str, Any]
    ) -> list[InputField] | None:
        return missing_required_inputs(node, context)

    def _auto_derive_condition_input(
        self, node: AOPNode, context: dict[str, Any]
    ) -> InputField | None:
        aggregated = self._collect_field_values(node.condition_field or "")
        return auto_derive_condition_input(
            node, context, aggregated_values=aggregated
        )

    def _collect_field_values(self, field: str) -> list[str]:
        return collect_field_values_for_field(field, self.nodes.values())

    async def _emit_node_event(
        self,
        session_id: str | None,
        node_id: str,
        node_type: str,
        outcome: str,
        context: dict[str, Any],
    ) -> None:
        if self._event_bus and session_id:
            from cen.telemetry.events import NodeExecutedEvent

            await self._event_bus.emit(
                NodeExecutedEvent(
                    session_id=session_id,
                    module=self.module_name,
                    node_id=node_id,
                    node_type=node_type,
                    outcome=outcome,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    context=context,
                )
            )

    def _collect_exclusive_branch(
        self, skip_root: str, keep_root: str, skip_set: set[str]
    ) -> None:
        collect_exclusive_branch(self.graph, skip_root, keep_root, skip_set)
