"""Per-node-type runtime handlers extracted from the engine.

The main ``AsyncWorkflowEngine.execute`` loop dispatches each node to
one of these handlers. Each handler receives an ``ExecutionState``
that bundles the mutable per-run state (executed list, skip set,
context, output cache, pause fields) and returns a ``StepResult``
telling the dispatcher whether to continue to the next node, break
out of the loop (pause/terminal), or proceed (run the rest of the
loop body — currently always equivalent to continue).

Pulled out of ``engine.py`` per CLAUDE.md §4.9 file-size discipline.
The behavior here is identical to the previous in-line implementation
— this is an extraction, not a redesign.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import networkx as nx

from cen.core.engine_helpers import collect_exclusive_branch, evaluate_condition
from cen.core.models import AOPNode, InputField

if TYPE_CHECKING:
    from cen.core.engine import AsyncWorkflowEngine


class StepResult(Enum):
    CONTINUE = "continue"
    BREAK = "break"


@dataclass
class ExecutionState:
    """All mutable state the handlers share during one execute() call."""

    context: dict[str, Any]
    executed: list[str] = field(default_factory=list)
    outcome: str = "completed"
    skip_set: set[str] = field(default_factory=set)
    pending_input_node: str | None = None
    pending_input_fields: list[InputField] | None = None
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    approved_nodes: set[str] = field(default_factory=set)


# ── ACTION ──────────────────────────────────────────────────────────


async def run_action_node(
    engine: "AsyncWorkflowEngine",
    node: AOPNode,
    state: ExecutionState,
    session_id: str | None,
) -> StepResult:
    cached = state.node_outputs.get(node.id)
    if cached is not None:
        # Replay: restore context fields without firing the LLM call.
        state.executed.append(node.id)
        for k, v in cached.items():
            state.context[k] = v
        await engine._emit_node_event(
            session_id, node.id, "ACTION", "done", state.context
        )
        return StepResult.CONTINUE

    # Pre-execution input check (Non-Negotiable for the step-pause flow).
    missing = engine._missing_required_inputs(node, state.context)
    if missing:
        state.pending_input_node = node.id
        state.pending_input_fields = missing
        state.outcome = f"pending_input:{node.metadata.label or node.id}"
        await engine._emit_node_event(
            session_id, node.id, "ACTION", "pending_input", state.context
        )
        return StepResult.BREAK

    # First-time execution.
    state.executed.append(node.id)
    output: dict[str, Any] = {}

    llm_prompt = node.metadata.params.get("llm_prompt")
    if llm_prompt and engine._llm:
        prompt = (
            llm_prompt.format(**state.context) if "{" in llm_prompt else llm_prompt
        )
        if engine._llm_semaphore:
            t0 = time.monotonic()
            async with engine._llm_semaphore:
                wait_time = time.monotonic() - t0
                if wait_time > 0.001 and engine._event_bus and session_id:
                    from cen.telemetry.events import LLMThrottledEvent

                    await engine._event_bus.emit(
                        LLMThrottledEvent(
                            session_id=session_id,
                            node_id=node.id,
                            wait_time=wait_time,
                        )
                    )
                llm_response = await engine._llm.generate(prompt)
        else:
            llm_response = await engine._llm.generate(prompt)
        state.context[f"{node.id}_llm_response"] = llm_response
        output[f"{node.id}_llm_response"] = llm_response

    state.context[f"{node.id}_status"] = "done"
    output[f"{node.id}_status"] = "done"

    # auto_set: declarative writes that fire after the node completes.
    if node.metadata.auto_set:
        for k, v in node.metadata.auto_set.items():
            state.context[k] = v
            output[k] = v

    state.node_outputs[node.id] = output
    await engine._emit_node_event(
        session_id, node.id, "ACTION", "done", state.context
    )
    return StepResult.CONTINUE


# ── CONDITION ───────────────────────────────────────────────────────


async def run_condition_node(
    engine: "AsyncWorkflowEngine",
    node: AOPNode,
    state: ExecutionState,
    session_id: str | None,
) -> StepResult:
    cached = state.node_outputs.get(node.id)

    # Input-collection pause (only on the first-time path).
    if cached is None:
        if node.metadata.input_schema:
            missing = engine._missing_required_inputs(node, state.context)
            if missing:
                state.pending_input_node = node.id
                state.pending_input_fields = missing
                state.outcome = f"pending_input:{node.metadata.label or node.id}"
                await engine._emit_node_event(
                    session_id, node.id, "CONDITION", "pending_input", state.context
                )
                return StepResult.BREAK
        else:
            auto_field = engine._auto_derive_condition_input(node, state.context)
            if auto_field is not None:
                state.pending_input_node = node.id
                state.pending_input_fields = [auto_field]
                state.outcome = f"pending_input:{node.metadata.label or node.id}"
                await engine._emit_node_event(
                    session_id, node.id, "CONDITION", "pending_input", state.context
                )
                return StepResult.BREAK

    state.executed.append(node.id)

    if cached is not None:
        # Replay path.
        for k, v in cached.items():
            state.context[k] = v
        if node.condition_operator == "switch" and node.branches:
            chosen = cached.get(f"{node.id}_result")
            await engine._emit_node_event(
                session_id, node.id, "CONDITION", f"switch:{chosen}", state.context
            )
            _apply_switch_skip(engine.graph, node, chosen, state.skip_set)
        else:
            result = cached.get(f"{node.id}_result")
            await engine._emit_node_event(
                session_id, node.id, "CONDITION",
                "true" if result else "false", state.context,
            )
            _apply_branch_skip(engine.graph, node, bool(result), state.skip_set)
        return StepResult.CONTINUE

    # First-time evaluation path.
    if node.condition_operator == "switch" and node.branches:
        actual = state.context.get(node.condition_field or "")
        chosen = node.branches.get(actual) if actual is not None else None
        state.context[f"{node.id}_result"] = chosen
        state.node_outputs[node.id] = {f"{node.id}_result": chosen}
        await engine._emit_node_event(
            session_id, node.id, "CONDITION", f"switch:{chosen}", state.context
        )
        _apply_switch_skip(engine.graph, node, chosen, state.skip_set)
        return StepResult.CONTINUE

    result = evaluate_condition(node, state.context)
    state.context[f"{node.id}_result"] = result
    state.node_outputs[node.id] = {f"{node.id}_result": result}
    await engine._emit_node_event(
        session_id, node.id, "CONDITION",
        "true" if result else "false", state.context,
    )
    _apply_branch_skip(engine.graph, node, result, state.skip_set)
    return StepResult.CONTINUE


def _apply_branch_skip(
    graph: nx.DiGraph, node: AOPNode, result: bool, skip_set: set[str]
) -> None:
    """For a binary CONDITION, mark the unselected branch's nodes as skipped."""
    if result:
        if node.false_next:
            collect_exclusive_branch(graph, node.false_next, node.true_next or "", skip_set)
    else:
        if node.true_next:
            collect_exclusive_branch(graph, node.true_next, node.false_next or "", skip_set)


def _apply_switch_skip(
    graph: nx.DiGraph, node: AOPNode, chosen: str | None, skip_set: set[str]
) -> None:
    """For a switch CONDITION, mark every non-chosen branch's nodes as skipped."""
    if not chosen or not node.branches:
        return
    keep_reachable: set[str] = set()
    if chosen in graph:
        keep_reachable = {chosen} | nx.descendants(graph, chosen)
    for target in set(node.branches.values()) - {chosen}:
        if target in graph:
            candidates = {target} | nx.descendants(graph, target)
            for n in candidates - keep_reachable:
                skip_set.add(n)


# ── HANDOFF ─────────────────────────────────────────────────────────


async def run_handoff_node(
    engine: "AsyncWorkflowEngine",
    node: AOPNode,
    state: ExecutionState,
    session_id: str | None,
) -> StepResult:
    cached = state.node_outputs.get(node.id)
    if cached is not None:
        state.executed.append(node.id)
        for k, v in cached.items():
            state.context[k] = v
        return StepResult.CONTINUE

    state.executed.append(node.id)
    handoff_output: dict[str, Any] = {}
    if node.metadata.auto_set:
        for k, v in node.metadata.auto_set.items():
            state.context[k] = v
            handoff_output[k] = v
    state.node_outputs[node.id] = handoff_output

    # `pause_on_handoff`: when the author flagged this HANDOFF as
    # waiting on a third party, the engine pauses (case becomes
    # AWAITING_EXTERNAL via the route layer). Default false keeps the
    # legacy behavior: HANDOFF logs and the workflow continues
    # (typically terminates because there are no downstream nodes).
    #
    # ``__resumed_external`` is the resume signal set by
    # ``/cases/{id}/resume_external`` — when true, this HANDOFF runs
    # through without pausing again so the workflow can advance.
    pause = bool(node.metadata.params.get("pause_on_handoff", False))
    resumed = bool(state.context.get("__resumed_external", False))
    if pause and not resumed:
        state.pending_input_node = node.id
        state.outcome = f"awaiting_external:{node.metadata.label or node.id}"
        await engine._emit_node_event(
            session_id, node.id, "HANDOFF", "awaiting_external", state.context
        )
        return StepResult.BREAK

    state.outcome = f"handoff:{node.metadata.label or node.id}"
    await engine._emit_node_event(
        session_id, node.id, "HANDOFF", state.outcome, state.context
    )
    return StepResult.CONTINUE


# ── APPROVAL ────────────────────────────────────────────────────────


async def run_approval_node(
    engine: "AsyncWorkflowEngine",
    node: AOPNode,
    state: ExecutionState,
    session_id: str | None,
) -> StepResult:
    cached = state.node_outputs.get(node.id)
    if cached is not None:
        # Replay without re-emitting the "approved" event.
        state.executed.append(node.id)
        for k, v in cached.items():
            state.context[k] = v
        return StepResult.CONTINUE

    if node.id in state.approved_nodes:
        state.executed.append(node.id)
        approval_output: dict[str, Any] = {f"{node.id}_status": "approved"}
        state.context[f"{node.id}_status"] = "approved"
        if node.metadata.auto_set:
            for k, v in node.metadata.auto_set.items():
                state.context[k] = v
                approval_output[k] = v
        state.node_outputs[node.id] = approval_output
        await engine._emit_node_event(
            session_id, node.id, "APPROVAL", "approved", state.context
        )
        return StepResult.CONTINUE

    # Pending — don't append, don't cache. Surface via pending_input_node
    # so the route layer can persist AWAITING_APPROVAL with the right id.
    state.pending_input_node = node.id
    state.outcome = f"pending_approval:{node.metadata.label or node.id}"
    await engine._emit_node_event(
        session_id, node.id, "APPROVAL", "pending_approval", state.context
    )
    return StepResult.BREAK
