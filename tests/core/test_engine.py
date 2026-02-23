"""Tests for AsyncWorkflowEngine."""

from __future__ import annotations

import asyncio
import time

import pytest

from cen.core.engine import AsyncWorkflowEngine
from cen.core.exceptions import CycleDetectedError
from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeType,
    WorkflowInput,
)
from cen.telemetry.bus import AsyncEventBus
from cen.telemetry.events import LLMThrottledEvent


def _simple_aop() -> AOPDefinition:
    """Linear: action_a -> condition_b -> action_true / action_false -> handoff."""
    return AOPDefinition(
        module_name="test_module",
        nodes=[
            AOPNode(id="a", type=NodeType.ACTION),
            AOPNode(
                id="b",
                type=NodeType.CONDITION,
                condition_field="val",
                condition_operator="<",
                condition_value=10,
                true_next="c_true",
                false_next="c_false",
            ),
            AOPNode(id="c_true", type=NodeType.ACTION),
            AOPNode(id="c_false", type=NodeType.ACTION),
            AOPNode(id="d", type=NodeType.HANDOFF),
        ],
        edges=[
            AOPEdge(source="a", target="b"),
            AOPEdge(source="b", target="c_true"),
            AOPEdge(source="b", target="c_false"),
            AOPEdge(source="c_true", target="d"),
            AOPEdge(source="c_false", target="d"),
        ],
    )


class TestLoadAOP:
    def test_loads_valid_aop(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_simple_aop())
        assert engine.module_name == "test_module"
        assert len(engine.nodes) == 5

    def test_rejects_cycle(self):
        aop = AOPDefinition(
            module_name="cyclic",
            nodes=[
                AOPNode(id="a", type=NodeType.ACTION),
                AOPNode(id="b", type=NodeType.ACTION),
            ],
            edges=[
                AOPEdge(source="a", target="b"),
                AOPEdge(source="b", target="a"),
            ],
        )
        engine = AsyncWorkflowEngine()
        with pytest.raises(CycleDetectedError):
            engine.load_aop(aop)


class TestExecute:
    @pytest.fixture()
    def engine(self) -> AsyncWorkflowEngine:
        e = AsyncWorkflowEngine()
        e.load_aop(_simple_aop())
        return e

    async def test_true_branch(self, engine: AsyncWorkflowEngine):
        result = await engine.execute(
            WorkflowInput(module_name="test_module", context={"val": 5})
        )
        assert "c_true" in result.executed_nodes
        assert "c_false" not in result.executed_nodes
        assert result.final_outcome.startswith("handoff:")

    async def test_false_branch(self, engine: AsyncWorkflowEngine):
        result = await engine.execute(
            WorkflowInput(module_name="test_module", context={"val": 15})
        )
        assert "c_false" in result.executed_nodes
        assert "c_true" not in result.executed_nodes

    async def test_execution_order(self, engine: AsyncWorkflowEngine):
        result = await engine.execute(
            WorkflowInput(module_name="test_module", context={"val": 5})
        )
        nodes = result.executed_nodes
        assert nodes.index("a") < nodes.index("b")
        assert nodes.index("b") < nodes.index("c_true")
        assert nodes.index("c_true") < nodes.index("d")


def _approval_aop() -> AOPDefinition:
    """Linear: action -> approval_gate -> handoff."""
    return AOPDefinition(
        module_name="approval_test",
        nodes=[
            AOPNode(id="step1", type=NodeType.ACTION),
            AOPNode(
                id="gate",
                type=NodeType.APPROVAL,
                metadata={"label": "Manager Approval", "description": "", "params": {}},
            ),
            AOPNode(id="final", type=NodeType.HANDOFF, metadata={"label": "Done"}),
        ],
        edges=[
            AOPEdge(source="step1", target="gate"),
            AOPEdge(source="gate", target="final"),
        ],
    )


class TestApprovalNode:
    @pytest.fixture()
    def engine(self) -> AsyncWorkflowEngine:
        e = AsyncWorkflowEngine()
        e.load_aop(_approval_aop())
        return e

    async def test_stops_at_unapproved_gate(self, engine: AsyncWorkflowEngine):
        result = await engine.execute(
            WorkflowInput(module_name="approval_test", context={})
        )
        assert result.final_outcome.startswith("pending_approval:")
        assert "gate" in result.executed_nodes
        assert "final" not in result.executed_nodes

    async def test_passes_through_approved_gate(self, engine: AsyncWorkflowEngine):
        result = await engine.execute(
            WorkflowInput(module_name="approval_test", context={}),
            approved_nodes={"gate"},
        )
        assert result.final_outcome.startswith("handoff:")
        assert "gate" in result.executed_nodes
        assert "final" in result.executed_nodes

    async def test_approved_gate_sets_status_in_context(self, engine: AsyncWorkflowEngine):
        result = await engine.execute(
            WorkflowInput(module_name="approval_test", context={}),
            approved_nodes={"gate"},
        )
        assert result.context["gate_status"] == "approved"


# ---------------------------------------------------------------------------
# Helpers for concurrency tests
# ---------------------------------------------------------------------------

def _llm_aop() -> AOPDefinition:
    """Single action node with an LLM prompt."""
    return AOPDefinition(
        module_name="llm_test",
        nodes=[
            AOPNode(
                id="llm_node",
                type=NodeType.ACTION,
                metadata={"label": "LLM call", "description": "", "params": {"llm_prompt": "hello"}},
            ),
        ],
        edges=[],
    )


class _SlowLLM:
    """Fake LLM that sleeps to simulate latency."""

    def __init__(self, delay: float = 0.15):
        self._delay = delay

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        await asyncio.sleep(self._delay)
        return "response"

    async def is_available(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "slow_mock"


# ---------------------------------------------------------------------------
# Concurrency limit tests
# ---------------------------------------------------------------------------

class TestConcurrencyLimits:
    async def test_semaphore_serializes_concurrent_calls(self):
        """With Semaphore(1), two concurrent executions should run serially."""
        sem = asyncio.Semaphore(1)
        slow_llm = _SlowLLM(delay=0.15)

        e1 = AsyncWorkflowEngine(llm=slow_llm, llm_semaphore=sem)
        e1.load_aop(_llm_aop())
        e2 = AsyncWorkflowEngine(llm=slow_llm, llm_semaphore=sem)
        e2.load_aop(_llm_aop())

        start = time.monotonic()
        r1, r2 = await asyncio.gather(
            e1.execute(WorkflowInput(module_name="llm_test", context={})),
            e2.execute(WorkflowInput(module_name="llm_test", context={})),
        )
        elapsed = time.monotonic() - start

        assert r1.context["llm_node_llm_response"] == "response"
        assert r2.context["llm_node_llm_response"] == "response"
        # Serialized: should take ~2x the single-call delay
        assert elapsed >= 0.25

    async def test_no_semaphore_backward_compat(self):
        """Engine without semaphore still works (no regression)."""
        slow_llm = _SlowLLM(delay=0.05)
        engine = AsyncWorkflowEngine(llm=slow_llm)
        engine.load_aop(_llm_aop())

        result = await engine.execute(
            WorkflowInput(module_name="llm_test", context={})
        )
        assert result.context["llm_node_llm_response"] == "response"

    async def test_throttle_event_emitted(self):
        """When the semaphore causes waiting, an LLMThrottledEvent is emitted."""
        sem = asyncio.Semaphore(1)
        bus = AsyncEventBus()
        captured: list[LLMThrottledEvent] = []

        async def capture(event: LLMThrottledEvent) -> None:
            captured.append(event)

        bus.subscribe(LLMThrottledEvent, capture)

        slow_llm = _SlowLLM(delay=0.15)
        e1 = AsyncWorkflowEngine(llm=slow_llm, event_bus=bus, llm_semaphore=sem)
        e1.load_aop(_llm_aop())
        e2 = AsyncWorkflowEngine(llm=slow_llm, event_bus=bus, llm_semaphore=sem)
        e2.load_aop(_llm_aop())

        await asyncio.gather(
            e1.execute(
                WorkflowInput(module_name="llm_test", context={}),
                session_id="s1",
            ),
            e2.execute(
                WorkflowInput(module_name="llm_test", context={}),
                session_id="s2",
            ),
        )

        # At least one of the two should have waited
        assert len(captured) >= 1
        evt = captured[0]
        assert evt.node_id == "llm_node"
        assert evt.wait_time > 0
