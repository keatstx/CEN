"""Tests for AsyncWorkflowEngine."""

from __future__ import annotations

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
