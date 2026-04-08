"""AsyncWorkflowEngine — executes AOP/DAG workflows with DI for LLM + EventBus."""

from __future__ import annotations

import asyncio
import operator
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import networkx as nx

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


def _humanize(s: str) -> str:
    """Turn 'approved_full' into 'Approved Full' for select labels."""
    return s.replace("_", " ").strip().title() if s else s


class AsyncWorkflowEngine:
    def __init__(
        self,
        llm: LanguageModel | None = None,
        event_bus: AsyncEventBus | None = None,
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

    def _evaluate_condition(self, node: AOPNode, context: dict[str, Any]) -> bool:
        field = node.condition_field
        op_str = node.condition_operator
        value = node.condition_value

        if field is None or op_str is None:
            return False

        # Allow comparing against another context field
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
            # Numeric ops require coercible values on both sides. If
            # coercion fails (e.g. user typed "test" into an auto-
            # derived text input for a numeric condition), treat the
            # comparison as False rather than crashing the engine.
            try:
                return op_func(float(actual), float(value))
            except (TypeError, ValueError):
                return False
        try:
            return op_func(actual, value)
        except TypeError:
            # Mismatched types on a non-numeric op (e.g. comparing a
            # string to an int via ==). Defensive: return False rather
            # than 500 the request.
            return False

    async def execute(
        self,
        workflow_input: WorkflowInput,
        approved_nodes: set[str] | None = None,
        session_id: str | None = None,
    ) -> WorkflowResult:
        start = time.time()
        context = dict(workflow_input.context)
        executed: list[str] = []
        outcome = "completed"
        _approved = approved_nodes or set()

        # Idempotency cache (CLAUDE.md non-negotiable #3): per-node outputs
        # from prior runs of this workflow. When the engine resumes after
        # an APPROVAL pause (or, in the future, an AWAITING_INPUT pause),
        # any node already in the cache replays its cached state instead
        # of re-executing — so LLM calls and external side effects fire
        # exactly once across the lifetime of a case.
        node_outputs: dict[str, dict[str, Any]] = dict(
            context.get("__node_outputs", {})
        )

        sorted_nodes = list(nx.topological_sort(self.graph))
        skip_set: set[str] = set()
        pending_input_node: str | None = None
        pending_input_fields: list[InputField] | None = None

        for node_id in sorted_nodes:
            if node_id in skip_set:
                continue

            node = self.nodes[node_id]

            if node.type == NodeType.ACTION:
                cached = node_outputs.get(node_id)
                if cached is not None:
                    # Replay: restore context fields written by the previous
                    # execution without firing the LLM call again.
                    executed.append(node_id)
                    for k, v in cached.items():
                        context[k] = v
                    await self._emit_node_event(
                        session_id, node_id, "ACTION", "done", context
                    )
                    continue

                # Pre-execution input check (CLAUDE.md non-negotiable for
                # the new step-pause flow). If the node declares an
                # input_schema and any required field is missing from
                # context, pause and ask the user.
                missing = self._missing_required_inputs(node, context)
                if missing:
                    pending_input_node = node_id
                    pending_input_fields = missing
                    outcome = f"pending_input:{node.metadata.label or node_id}"
                    await self._emit_node_event(
                        session_id, node_id, "ACTION", "pending_input", context
                    )
                    break

                # First-time execution path.
                executed.append(node_id)
                output: dict[str, Any] = {}
                llm_prompt = node.metadata.params.get("llm_prompt")
                if llm_prompt and self._llm:
                    prompt = llm_prompt.format(**context) if "{" in llm_prompt else llm_prompt
                    if self._llm_semaphore:
                        t0 = time.monotonic()
                        async with self._llm_semaphore:
                            wait_time = time.monotonic() - t0
                            if wait_time > 0.001 and self._event_bus and session_id:
                                from cen.telemetry.events import LLMThrottledEvent

                                await self._event_bus.emit(
                                    LLMThrottledEvent(
                                        session_id=session_id,
                                        node_id=node_id,
                                        wait_time=wait_time,
                                    )
                                )
                            llm_response = await self._llm.generate(prompt)
                    else:
                        llm_response = await self._llm.generate(prompt)
                    context[f"{node_id}_llm_response"] = llm_response
                    output[f"{node_id}_llm_response"] = llm_response
                context[f"{node_id}_status"] = "done"
                output[f"{node_id}_status"] = "done"
                # Apply auto_set: any context fields the node author
                # declared as "set this after I finish". Used to bridge
                # ACTION → downstream CONDITION gaps so the navigator
                # isn't asked redundant boolean questions.
                if node.metadata.auto_set:
                    for k, v in node.metadata.auto_set.items():
                        context[k] = v
                        output[k] = v
                node_outputs[node_id] = output
                await self._emit_node_event(session_id, node_id, "ACTION", "done", context)

            elif node.type == NodeType.CONDITION:
                cached = node_outputs.get(node_id)
                if cached is None:
                    # Auto-pause if the condition field is missing from
                    # context. The frontend will render a single input
                    # for the user to fill in, then the engine resumes
                    # and re-evaluates the condition.
                    auto_field = self._auto_derive_condition_input(node, context)
                    if auto_field is not None:
                        pending_input_node = node_id
                        pending_input_fields = [auto_field]
                        outcome = f"pending_input:{node.metadata.label or node_id}"
                        await self._emit_node_event(
                            session_id, node_id, "CONDITION", "pending_input", context
                        )
                        break

                executed.append(node_id)

                if cached is not None:
                    # Replay: restore the prior result and apply the same
                    # branch-skip behavior so resumed runs follow the same
                    # path through the DAG.
                    for k, v in cached.items():
                        context[k] = v
                    if node.condition_operator == "switch" and node.branches:
                        chosen = cached.get(f"{node_id}_result")
                        await self._emit_node_event(
                            session_id, node_id, "CONDITION", f"switch:{chosen}", context
                        )
                        if chosen:
                            keep_reachable = (
                                {chosen} | nx.descendants(self.graph, chosen)
                                if chosen in self.graph
                                else set()
                            )
                            for target in set(node.branches.values()) - {chosen}:
                                if target in self.graph:
                                    candidates = {target} | nx.descendants(self.graph, target)
                                    for n in candidates - keep_reachable:
                                        skip_set.add(n)
                    else:
                        result = cached.get(f"{node_id}_result")
                        await self._emit_node_event(
                            session_id, node_id, "CONDITION",
                            "true" if result else "false", context,
                        )
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
                    continue

                # First-time execution path.

                # Multi-way switch router
                if node.condition_operator == "switch" and node.branches:
                    actual = context.get(node.condition_field or "")
                    chosen = node.branches.get(actual) if actual is not None else None
                    context[f"{node_id}_result"] = chosen
                    node_outputs[node_id] = {f"{node_id}_result": chosen}
                    await self._emit_node_event(
                        session_id, node_id, "CONDITION", f"switch:{chosen}", context
                    )
                    all_targets = set(node.branches.values())
                    if chosen:
                        keep_reachable = {chosen} | nx.descendants(self.graph, chosen) \
                            if chosen in self.graph else set()
                        for target in all_targets - {chosen}:
                            if target in self.graph:
                                candidates = {target} | nx.descendants(self.graph, target)
                                for n in candidates - keep_reachable:
                                    skip_set.add(n)
                    continue

                result = self._evaluate_condition(node, context)
                context[f"{node_id}_result"] = result
                node_outputs[node_id] = {f"{node_id}_result": result}
                await self._emit_node_event(
                    session_id, node_id, "CONDITION", "true" if result else "false", context
                )

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
                await self._emit_node_event(session_id, node_id, "HANDOFF", outcome, context)

            elif node.type == NodeType.APPROVAL:
                executed.append(node_id)
                if node_id in _approved:
                    context[f"{node_id}_status"] = "approved"
                    # Apply auto_set on approval too — e.g. hipaa_consent
                    # auto-sets consent_granted=true so the downstream
                    # consent_check CONDITION advances cleanly.
                    if node.metadata.auto_set:
                        for k, v in node.metadata.auto_set.items():
                            context[k] = v
                    await self._emit_node_event(session_id, node_id, "APPROVAL", "approved", context)
                else:
                    outcome = f"pending_approval:{node.metadata.label or node_id}"
                    await self._emit_node_event(session_id, node_id, "APPROVAL", "pending_approval", context)
                    break

        # Persist the per-node output cache back into the workflow context
        # so the session_store round-trips it on save/resume.
        context["__node_outputs"] = node_outputs

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
            pending_node=pending_input_node,
            pending_input_fields=pending_input_fields,
        )

    @staticmethod
    def _missing_required_inputs(
        node: AOPNode, context: dict[str, Any]
    ) -> list[InputField] | None:
        """Return the subset of an ACTION node's input_schema whose required
        fields are missing from context. Returns None if nothing is missing
        (so the engine can continue) or there is no schema declared.
        """
        schema = node.metadata.input_schema
        if not schema:
            return None
        missing = [f for f in schema if f.required and context.get(f.key) is None]
        return missing or None

    def _auto_derive_condition_input(
        self, node: AOPNode, context: dict[str, Any]
    ) -> InputField | None:
        """Auto-derive an input prompt for a CONDITION node when its
        condition_field is missing from context. Returns None when the
        field is present (engine proceeds normally) or when the node has
        no condition_field at all (e.g. malformed switch node — let the
        existing evaluation path handle it).

        The field type is inferred from the condition_operator and
        condition_value, with multi-choice CONDITIONs aggregating
        sibling tested values across the DAG so the user gets a real
        dropdown of every legitimate value:

        - Switch with branches dict → select with branch keys as options
        - Numeric operators (<, <=, >, >=) → number input
        - "in [list]" operator → select with the list as options
        - Equality (==) against a non-bool value → select with the
          aggregated values across every other CONDITION in the DAG
          that reads the same field. If only one value exists, falls
          back to a 2-option select ("yes that value" / "no, other").
        - Bool condition_value → checkbox
        - Otherwise → text input
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
                {"value": str(k), "label": _humanize(str(k))}
                for k in node.branches.keys()
            ]
        elif op in NUMERIC_OPS:
            field_type = "number"
        elif op in ("in", "not in") and isinstance(value, (list, tuple)):
            field_type = "select"
            options = [
                {"value": str(v), "label": _humanize(str(v))} for v in value
            ]
        elif isinstance(value, bool):
            field_type = "boolean"
        elif op in ("==", "!="):
            # Aggregate every value tested for this field across the
            # DAG so the user sees a real choice list. This catches
            # the common pattern of multiple sibling CONDITIONs each
            # checking one possible value of the same field.
            aggregated = self._collect_field_values(field)
            if len(aggregated) >= 2:
                field_type = "select"
                options = [
                    {"value": str(v), "label": _humanize(str(v))} for v in aggregated
                ]
            elif len(aggregated) == 1:
                # Only one comparison value — make it a binary select
                # so the navigator can pick "this value" vs "anything
                # else", which still produces a meaningful boolean.
                only = next(iter(aggregated))
                field_type = "select"
                options = [
                    {"value": str(only), "label": _humanize(str(only))},
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

    def _collect_field_values(self, field: str) -> list[str]:
        """Walk the loaded DAG and return every distinct value tested
        against the given context field across all CONDITION nodes,
        in document order. Used to aggregate option lists for
        auto-derived multi-choice inputs."""
        seen: list[str] = []
        for n in self.nodes.values():
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
        """Skip nodes reachable only from skip_root and not from keep_root."""
        if skip_root not in self.graph:
            return
        skip_candidates = {skip_root} | nx.descendants(self.graph, skip_root)
        keep_reachable: set[str] = set()
        if keep_root and keep_root in self.graph:
            keep_reachable = {keep_root} | nx.descendants(self.graph, keep_root)
        for node in skip_candidates - keep_reachable:
            skip_set.add(node)
