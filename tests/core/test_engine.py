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
    InputField,
    NodeMetadata,
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


# ---------------------------------------------------------------------------
# Resume idempotency tests (CLAUDE.md non-negotiable #3)
# ---------------------------------------------------------------------------

class _CallCountingLLM:
    """Fake LLM that records every call so tests can assert exact-once semantics."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        self.calls.append(prompt)
        return f"response_{len(self.calls)}"

    async def is_available(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "counting_mock"


def _resume_aop() -> AOPDefinition:
    """ACTION (LLM) -> CONDITION -> ACTION (LLM) -> APPROVAL -> ACTION (LLM) -> HANDOFF.

    Has two LLM ACTION nodes before the approval gate, one after. Used to
    verify that resuming after the gate does not re-fire the pre-gate LLMs.
    """
    return AOPDefinition(
        module_name="resume_test",
        nodes=[
            AOPNode(
                id="pre1",
                type=NodeType.ACTION,
                metadata={
                    "label": "Pre-gate LLM 1",
                    "description": "",
                    "params": {"llm_prompt": "first prompt"},
                },
            ),
            AOPNode(
                id="branch",
                type=NodeType.CONDITION,
                condition_field="route",
                condition_operator="==",
                condition_value="A",
                true_next="pre2",
                false_next="skipped_branch",
            ),
            AOPNode(
                id="pre2",
                type=NodeType.ACTION,
                metadata={
                    "label": "Pre-gate LLM 2",
                    "description": "",
                    "params": {"llm_prompt": "second prompt"},
                },
            ),
            AOPNode(id="skipped_branch", type=NodeType.ACTION),
            AOPNode(
                id="gate",
                type=NodeType.APPROVAL,
                metadata={"label": "Manager Approval", "description": "", "params": {}},
            ),
            AOPNode(
                id="post",
                type=NodeType.ACTION,
                metadata={
                    "label": "Post-gate LLM",
                    "description": "",
                    "params": {"llm_prompt": "third prompt"},
                },
            ),
            AOPNode(id="done", type=NodeType.HANDOFF, metadata={"label": "Done"}),
        ],
        edges=[
            AOPEdge(source="pre1", target="branch"),
            AOPEdge(source="branch", target="pre2"),
            AOPEdge(source="branch", target="skipped_branch"),
            AOPEdge(source="pre2", target="gate"),
            AOPEdge(source="skipped_branch", target="gate"),
            AOPEdge(source="gate", target="post"),
            AOPEdge(source="post", target="done"),
        ],
    )


class TestResumeIdempotency:
    """Verifies CLAUDE.md non-negotiable #3: side effects fire exactly once
    across pause/resume. The cache lives in context["__node_outputs"]."""

    async def test_first_run_pauses_at_gate_and_caches_outputs(self):
        llm = _CallCountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_resume_aop())

        result = await engine.execute(
            WorkflowInput(module_name="resume_test", context={"route": "A"})
        )

        # Workflow paused at the gate.
        assert result.final_outcome.startswith("pending_approval:")
        # Both pre-gate LLM nodes ran exactly once.
        assert len(llm.calls) == 2
        # Cache contains the executed nodes (pre1, branch, pre2, gate
        # — gate is APPROVAL and isn't cached, but the others are).
        cache = result.context["__node_outputs"]
        assert "pre1" in cache
        assert "branch" in cache
        assert "pre2" in cache
        assert "pre1_llm_response" in cache["pre1"]
        assert cache["pre1"]["pre1_llm_response"] == "response_1"
        assert cache["pre2"]["pre2_llm_response"] == "response_2"

    async def test_resume_does_not_replay_pre_gate_llm_calls(self):
        llm = _CallCountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_resume_aop())

        # First run: pauses at gate, makes 2 LLM calls.
        first = await engine.execute(
            WorkflowInput(module_name="resume_test", context={"route": "A"})
        )
        assert len(llm.calls) == 2

        # Resume: pass the saved context (which now contains __node_outputs)
        # back in along with the approved gate. Critical: pre1 and pre2 must
        # NOT fire again. Only the post-gate LLM (post) fires.
        second = await engine.execute(
            WorkflowInput(module_name="resume_test", context=first.context),
            approved_nodes={"gate"},
        )

        # Total LLM calls is now 3: 2 from the first run + 1 from the resume.
        # If the cache failed, it would be 4 (pre1 + pre2 re-fired).
        assert len(llm.calls) == 3
        assert llm.calls[2] == "third prompt"
        assert second.final_outcome.startswith("handoff:")

    async def test_cached_action_replays_response_into_context(self):
        llm = _CallCountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_resume_aop())

        first = await engine.execute(
            WorkflowInput(module_name="resume_test", context={"route": "A"})
        )
        first_response = first.context["pre1_llm_response"]

        second = await engine.execute(
            WorkflowInput(module_name="resume_test", context=first.context),
            approved_nodes={"gate"},
        )

        # The cached response is restored into the resumed context unchanged.
        assert second.context["pre1_llm_response"] == first_response
        assert second.context["pre2_llm_response"] == first.context["pre2_llm_response"]

    async def test_cached_condition_keeps_branch_decision_stable(self):
        llm = _CallCountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_resume_aop())

        # First run with route="A": branch goes to pre2.
        first = await engine.execute(
            WorkflowInput(module_name="resume_test", context={"route": "A"})
        )
        assert "pre2" in first.executed_nodes
        assert "skipped_branch" not in first.executed_nodes

        # Tamper with the route field on resume — the cached condition
        # result should still pin us to the original branch.
        tampered_context = dict(first.context)
        tampered_context["route"] = "B"

        second = await engine.execute(
            WorkflowInput(module_name="resume_test", context=tampered_context),
            approved_nodes={"gate"},
        )

        # Still in the original branch despite the tampered field — the
        # cached condition result wins.
        assert "pre2" in second.executed_nodes
        assert "skipped_branch" not in second.executed_nodes

    async def test_no_cache_on_fresh_context_runs_normally(self):
        llm = _CallCountingLLM()
        engine = AsyncWorkflowEngine(llm=llm)
        engine.load_aop(_resume_aop())

        # Two completely separate runs (different cases) should each
        # fire all the pre-gate LLMs.
        await engine.execute(
            WorkflowInput(module_name="resume_test", context={"route": "A"})
        )
        await engine.execute(
            WorkflowInput(module_name="resume_test", context={"route": "A"})
        )
        # Each run fires pre1 + pre2 = 2; total = 4.
        assert len(llm.calls) == 4


# ---------------------------------------------------------------------------
# Step-pause tests (CLAUDE.md non-negotiable for new Executor)
# ---------------------------------------------------------------------------

def _input_schema_aop() -> AOPDefinition:
    """ACTION node with declarative input_schema -> HANDOFF.

    The action requires `household_size` and optionally `notes` before
    it can run. The engine should pause with the schema fields when
    the required field is missing.
    """
    return AOPDefinition(
        module_name="input_schema_test",
        nodes=[
            AOPNode(
                id="collect",
                type=NodeType.ACTION,
                metadata=NodeMetadata(
                    label="Collect household size",
                    description="We need this to determine eligibility.",
                    params={},
                    input_schema=[
                        InputField(
                            key="household_size",
                            label="Household size",
                            type="number",
                            required=True,
                        ),
                        InputField(
                            key="notes",
                            label="Notes",
                            type="text",
                            required=False,
                        ),
                    ],
                ),
            ),
            AOPNode(id="done", type=NodeType.HANDOFF, metadata={"label": "Done"}),
        ],
        edges=[AOPEdge(source="collect", target="done")],
    )


def _condition_only_aop() -> AOPDefinition:
    """ACTION -> CONDITION (auto-pause if condition_field missing) -> two ACTIONs.

    The CONDITION reads `income_band` from context. If absent, the
    engine auto-derives an InputField and pauses without anyone
    declaring an input_schema.
    """
    return AOPDefinition(
        module_name="condition_pause_test",
        nodes=[
            AOPNode(id="start", type=NodeType.ACTION),
            AOPNode(
                id="check",
                type=NodeType.CONDITION,
                metadata=NodeMetadata(
                    label="Income band check",
                    description="Determines eligibility tier.",
                    params={},
                ),
                condition_field="income_band",
                condition_operator="==",
                condition_value="low",
                true_next="low_path",
                false_next="other_path",
            ),
            AOPNode(id="low_path", type=NodeType.ACTION),
            AOPNode(id="other_path", type=NodeType.ACTION),
            AOPNode(id="done", type=NodeType.HANDOFF, metadata={"label": "Done"}),
        ],
        edges=[
            AOPEdge(source="start", target="check"),
            AOPEdge(source="check", target="low_path"),
            AOPEdge(source="check", target="other_path"),
            AOPEdge(source="low_path", target="done"),
            AOPEdge(source="other_path", target="done"),
        ],
    )


class TestActionInputSchemaPause:
    async def test_pauses_when_required_field_missing(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_input_schema_aop())

        result = await engine.execute(
            WorkflowInput(module_name="input_schema_test", context={})
        )

        assert result.final_outcome.startswith("pending_input:")
        assert result.pending_node == "collect"
        assert result.pending_input_fields is not None
        # Only the required field is reported as missing.
        keys = [f.key for f in result.pending_input_fields]
        assert "household_size" in keys
        assert "notes" not in keys
        # The action did not execute.
        assert "collect" not in result.executed_nodes

    async def test_proceeds_when_required_field_present(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_input_schema_aop())

        result = await engine.execute(
            WorkflowInput(
                module_name="input_schema_test",
                context={"household_size": 4},
            )
        )

        assert result.final_outcome.startswith("handoff:")
        assert "collect" in result.executed_nodes
        assert "done" in result.executed_nodes
        assert result.pending_input_fields is None

    async def test_resume_after_input_provided(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_input_schema_aop())

        # First run pauses.
        first = await engine.execute(
            WorkflowInput(module_name="input_schema_test", context={})
        )
        assert first.final_outcome.startswith("pending_input:")

        # User provides the input — merge it into context, resume.
        merged = dict(first.context)
        merged["household_size"] = 6
        second = await engine.execute(
            WorkflowInput(module_name="input_schema_test", context=merged)
        )
        assert second.final_outcome.startswith("handoff:")
        assert "collect" in second.executed_nodes


class TestConditionAutoPause:
    async def test_auto_pauses_when_condition_field_missing(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_condition_only_aop())

        result = await engine.execute(
            WorkflowInput(module_name="condition_pause_test", context={})
        )

        assert result.final_outcome.startswith("pending_input:")
        assert result.pending_node == "check"
        assert result.pending_input_fields is not None
        assert len(result.pending_input_fields) == 1
        assert result.pending_input_fields[0].key == "income_band"
        # The earlier ACTION ran; the CONDITION did not.
        assert "start" in result.executed_nodes
        assert "check" not in result.executed_nodes

    async def test_proceeds_when_condition_field_present(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_condition_only_aop())

        result = await engine.execute(
            WorkflowInput(
                module_name="condition_pause_test", context={"income_band": "low"}
            )
        )

        assert result.final_outcome.startswith("handoff:")
        assert "check" in result.executed_nodes
        assert "low_path" in result.executed_nodes
        assert "other_path" not in result.executed_nodes

    async def test_auto_derived_input_type_for_numeric_condition_is_number(self):
        # Regression: previously the auto-derived InputField for any
        # CONDITION node was always type=text. When the condition
        # operator was numeric (<, >, etc.), the user would type a
        # string into the text field and the engine would crash with
        # `TypeError: '>' not supported between instances of 'str'
        # and 'int'`. The fix is to infer the field type from the
        # condition operator.
        aop = AOPDefinition(
            module_name="numeric_cond_test",
            nodes=[
                AOPNode(id="start", type=NodeType.ACTION),
                AOPNode(
                    id="check",
                    type=NodeType.CONDITION,
                    metadata=NodeMetadata(label="How many days remain?"),
                    condition_field="days_remaining",
                    condition_operator=">",
                    condition_value=0,
                    true_next="ok_path",
                    false_next="late_path",
                ),
                AOPNode(id="ok_path", type=NodeType.HANDOFF),
                AOPNode(id="late_path", type=NodeType.HANDOFF),
            ],
            edges=[
                AOPEdge(source="start", target="check"),
                AOPEdge(source="check", target="ok_path"),
                AOPEdge(source="check", target="late_path"),
            ],
        )
        engine = AsyncWorkflowEngine()
        engine.load_aop(aop)

        result = await engine.execute(
            WorkflowInput(module_name="numeric_cond_test", context={})
        )

        assert result.final_outcome.startswith("pending_input:")
        assert result.pending_input_fields is not None
        field = result.pending_input_fields[0]
        assert field.key == "days_remaining"
        assert field.type == "number", (
            f"expected numeric input type for numeric condition, got {field.type}"
        )

    async def test_evaluate_condition_returns_false_on_type_mismatch(self):
        # Regression: previously a string-vs-int comparison via a
        # numeric operator (e.g. user typed "test" into a deadline
        # check) would raise TypeError and crash the request with a
        # 500. The engine now returns False on un-coercible numeric
        # operands instead of crashing.
        aop = AOPDefinition(
            module_name="bad_types_test",
            nodes=[
                AOPNode(
                    id="check",
                    type=NodeType.CONDITION,
                    condition_field="x",
                    condition_operator=">",
                    condition_value=10,
                    true_next="t",
                    false_next="f",
                ),
                AOPNode(id="t", type=NodeType.HANDOFF),
                AOPNode(id="f", type=NodeType.HANDOFF),
            ],
            edges=[
                AOPEdge(source="check", target="t"),
                AOPEdge(source="check", target="f"),
            ],
        )
        engine = AsyncWorkflowEngine()
        engine.load_aop(aop)

        # Pass a string value where a number is expected — should
        # return False and continue, not crash.
        result = await engine.execute(
            WorkflowInput(module_name="bad_types_test", context={"x": "not a number"})
        )
        assert result.final_outcome.startswith("handoff:")
        # False branch was taken (since the comparison is False).
        assert "f" in result.executed_nodes
        assert "t" not in result.executed_nodes

    async def test_resume_after_condition_input_takes_correct_branch(self):
        engine = AsyncWorkflowEngine()
        engine.load_aop(_condition_only_aop())

        # First run pauses at the condition.
        first = await engine.execute(
            WorkflowInput(module_name="condition_pause_test", context={})
        )
        assert first.final_outcome.startswith("pending_input:")

        # Resume with income_band="other" — should take the false branch.
        merged = dict(first.context)
        merged["income_band"] = "other"
        second = await engine.execute(
            WorkflowInput(module_name="condition_pause_test", context=merged)
        )
        assert second.final_outcome.startswith("handoff:")
        assert "other_path" in second.executed_nodes
        assert "low_path" not in second.executed_nodes
