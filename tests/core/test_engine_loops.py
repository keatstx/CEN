"""Tests for bounded loop regions (LDCG).

Covers the spec's acceptance criteria: valid region loads / unannotated
cycle rejected (AC-L1), body runs the expected number of times with
side-effects fired once per iteration and idempotent on resume (AC-L2),
cap-without-exit escalates to the human gate and is recorded (AC-L3).
"""

from __future__ import annotations

import pytest

from cen.core.engine import AsyncWorkflowEngine
from cen.core.exceptions import CycleDetectedError
from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    LoopSpec,
    NodeMetadata,
    NodeType,
    WorkflowInput,
)
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.events import NodeExecutedEvent


class _CountingLLM:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        self.calls.append(prompt)
        return f"resp_{len(self.calls)}"

    async def is_available(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "counting"


def _loop_aop(max_iterations: int = 3) -> AOPDefinition:
    """enter(loop) -> work(side-effecting) -> check(exit) ; loop_back check->enter.
    check -> continue (resolve branch) ; check -> escalate (APPROVAL, on_limit_next)."""
    return AOPDefinition(
        module_name="loop_test",
        nodes=[
            AOPNode(
                id="enter",
                type=NodeType.ACTION,
                metadata=NodeMetadata(
                    label="Enter loop",
                    loop=LoopSpec(
                        exit_node="check",
                        exit_condition_field="settled",
                        exit_when="truthy",
                        max_iterations=max_iterations,
                        on_limit_next="escalate",
                    ),
                ),
            ),
            AOPNode(
                id="work",
                type=NodeType.ACTION,
                metadata=NodeMetadata(label="Do work", params={"llm_prompt": "negotiate"}),
            ),
            AOPNode(id="check", type=NodeType.ACTION, metadata=NodeMetadata(label="Round check")),
            AOPNode(id="continue", type=NodeType.ACTION, metadata=NodeMetadata(label="Settled")),
            AOPNode(id="escalate", type=NodeType.APPROVAL, metadata=NodeMetadata(label="Supervisor review")),
        ],
        edges=[
            AOPEdge(source="enter", target="work"),
            AOPEdge(source="work", target="check"),
            AOPEdge(source="check", target="enter", kind="loop_back"),
            AOPEdge(source="check", target="continue"),
            AOPEdge(source="check", target="escalate"),
        ],
    )


class TestLoadValidation:
    def test_valid_region_loads(self):  # AC-L1
        engine = AsyncWorkflowEngine()
        engine.load_aop(_loop_aop())
        assert "enter" in engine._loop_regions
        region = engine._loop_regions["enter"]
        assert region.exit == "check"
        assert region.continue_next == "continue"
        assert region.members == frozenset({"enter", "work", "check"})

    def test_unannotated_cycle_still_rejected(self):  # AC-L1
        aop = AOPDefinition(
            module_name="bad",
            nodes=[
                AOPNode(id="a", type=NodeType.ACTION),
                AOPNode(id="b", type=NodeType.ACTION),
            ],
            edges=[  # cycle with no loop metadata / no loop_back kind
                AOPEdge(source="a", target="b"),
                AOPEdge(source="b", target="a"),
            ],
        )
        with pytest.raises(CycleDetectedError):
            AsyncWorkflowEngine().load_aop(aop)


class TestLoopExecution:
    @pytest.mark.asyncio
    async def test_exit_on_first_pass_runs_body_once(self):  # AC-L2
        llm = _CountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_loop_aop())
        result = await engine.execute(
            WorkflowInput(module_name="loop_test", context={"settled": True})
        )
        assert len(llm.calls) == 1  # body fired exactly once
        assert "continue" in result.executed_nodes  # resolve branch taken
        assert "escalate" not in result.executed_nodes
        assert result.context["__loop_state"]["enter"]["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_cap_without_exit_escalates(self):  # AC-L2 + AC-L3
        llm = _CountingLLM()
        bus = AsyncEventBus()
        seen: list[NodeExecutedEvent] = []

        async def _capture(e: NodeExecutedEvent) -> None:
            seen.append(e)

        bus.subscribe(NodeExecutedEvent, _capture)
        engine = AsyncWorkflowEngine(llm=llm, event_bus=bus)
        engine.load_aop(_loop_aop(max_iterations=3))
        result = await engine.execute(
            WorkflowInput(module_name="loop_test", context={"settled": False}),
            session_id="s1",
        )
        assert len(llm.calls) == 3  # body fired once per iteration, capped at 3
        assert result.pending_node == "escalate"  # paused at the human gate
        assert result.context["__loop_state"]["enter"]["status"] == "escalated"
        assert "continue" not in result.executed_nodes  # resolve branch skipped
        loop_events = [e for e in seen if e.node_type == "LOOP"]
        assert loop_events and loop_events[0].outcome.startswith("escalated")

    @pytest.mark.asyncio
    async def test_escalation_resume_is_idempotent(self):  # AC-L2 resume
        llm = _CountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_loop_aop(max_iterations=3))
        first = await engine.execute(
            WorkflowInput(module_name="loop_test", context={"settled": False})
        )
        assert len(llm.calls) == 3
        # Resume with the escalation gate approved — the body must NOT re-run.
        await engine.execute(
            WorkflowInput(module_name="loop_test", context=first.context),
            approved_nodes={"escalate"},
        )
        assert len(llm.calls) == 3  # still 3 — no regeneration on resume
