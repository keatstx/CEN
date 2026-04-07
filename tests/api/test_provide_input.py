"""End-to-end tests for the /sessions/{id}/provide_input flow.

Drives the new step-pause mechanism through the API: create case →
execute → engine pauses at AWAITING_INPUT → provide_input → engine
resumes from cached outputs and runs to completion.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.api.app import create_app
from cen.api.dependencies import (
    get_audit_store,
    get_engines,
    get_project_store,
    get_session_store,
)
from cen.config import Settings
from cen.core.engine import AsyncWorkflowEngine
from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    InputField,
    NodeMetadata,
    NodeType,
)


def _pause_aop() -> AOPDefinition:
    """ACTION (no input needed) -> ACTION (declares input_schema for `goal`) -> HANDOFF."""
    return AOPDefinition(
        module_name="pause_test",
        nodes=[
            AOPNode(id="start", type=NodeType.ACTION),
            AOPNode(
                id="collect_goal",
                type=NodeType.ACTION,
                metadata=NodeMetadata(
                    label="What is your goal?",
                    description="Used to tailor the workflow.",
                    params={},
                    input_schema=[
                        InputField(
                            key="goal",
                            label="Goal",
                            type="text",
                            required=True,
                        ),
                    ],
                ),
            ),
            AOPNode(id="done", type=NodeType.HANDOFF, metadata={"label": "Done"}),
        ],
        edges=[
            AOPEdge(source="start", target="collect_goal"),
            AOPEdge(source="collect_goal", target="done"),
        ],
    )


@pytest.fixture()
async def pause_client():
    settings = Settings(
        llm_backend="mock",
        log_renderer="console",
        pii_backend="regex",
        db_path=":memory:",
    )
    app = create_app(settings)
    await get_session_store().initialize()
    await get_project_store().initialize()
    await get_audit_store().initialize()
    # Inject a custom engine for the pause_test module so we drive a
    # known input-schema flow without modifying the shipped JSON modules.
    engines = get_engines()
    eng = AsyncWorkflowEngine()
    eng.load_aop(_pause_aop())
    engines["pause_test"] = eng

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await get_audit_store().close()
    await get_project_store().close()
    await get_session_store().close()
    engines.pop("pause_test", None)


class TestProvideInputFlow:
    async def test_create_case_triggers_pause_via_execute(
        self, pause_client: AsyncClient
    ):
        # Create case.
        cr = await pause_client.post(
            "/cases", json={"module_name": "pause_test"}
        )
        assert cr.status_code == 201
        cid = cr.json()["id"]

        # Execute against the case — should pause at the input-collection node.
        ex = await pause_client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "pause_test", "context": {}},
        )
        assert ex.status_code == 200
        result = ex.json()
        assert result["final_outcome"].startswith("pending_input:")
        assert result["pending_node"] == "collect_goal"
        assert result["pending_input_fields"] is not None
        assert result["pending_input_fields"][0]["key"] == "goal"

        # The session row reflects AWAITING_INPUT.
        get = await pause_client.get(f"/cases/{cid}")
        assert get.status_code == 200
        assert get.json()["status"] == "AWAITING_INPUT"
        assert get.json()["pending_node"] == "collect_goal"
        assert get.json()["pending_input_fields"] is not None
        assert get.json()["pending_input_fields"][0]["key"] == "goal"

    async def test_provide_input_resumes_to_completion(
        self, pause_client: AsyncClient
    ):
        cr = await pause_client.post(
            "/cases", json={"module_name": "pause_test"}
        )
        cid = cr.json()["id"]
        await pause_client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "pause_test", "context": {}},
        )

        # Provide the input.
        resp = await pause_client.post(
            f"/cases/{cid}/provide_input",
            json={"inputs": {"goal": "reduce my medical debt"}},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["final_outcome"].startswith("handoff:")
        assert "collect_goal" in result["executed_nodes"]
        assert "done" in result["executed_nodes"]

        # The session row is now COMPLETED with the input merged into context.
        get = await pause_client.get(f"/cases/{cid}")
        assert get.json()["status"] == "COMPLETED"
        assert get.json()["pending_input_fields"] is None
        assert get.json()["context"]["goal"] == "reduce my medical debt"

    async def test_provide_input_when_not_awaiting_returns_409(
        self, pause_client: AsyncClient
    ):
        # Fresh case in ACTIVE status — provide_input should be rejected.
        cr = await pause_client.post(
            "/cases", json={"module_name": "pause_test"}
        )
        cid = cr.json()["id"]
        resp = await pause_client.post(
            f"/cases/{cid}/provide_input",
            json={"inputs": {"goal": "x"}},
        )
        assert resp.status_code == 409

    async def test_provide_input_missing_required_field_returns_422(
        self, pause_client: AsyncClient
    ):
        cr = await pause_client.post(
            "/cases", json={"module_name": "pause_test"}
        )
        cid = cr.json()["id"]
        await pause_client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "pause_test", "context": {}},
        )

        # Submit empty inputs — required field missing.
        resp = await pause_client.post(
            f"/cases/{cid}/provide_input",
            json={"inputs": {}},
        )
        assert resp.status_code == 422
        assert "goal" in resp.text

    async def test_provide_input_via_sessions_alias(
        self, pause_client: AsyncClient
    ):
        # The /sessions alias should work identically.
        cr = await pause_client.post(
            "/sessions", json={"module_name": "pause_test"}
        )
        cid = cr.json()["id"]
        await pause_client.post(
            f"/execute?session_id={cid}",
            json={"module_name": "pause_test", "context": {}},
        )
        resp = await pause_client.post(
            f"/sessions/{cid}/provide_input",
            json={"inputs": {"goal": "test"}},
        )
        assert resp.status_code == 200
        assert resp.json()["final_outcome"].startswith("handoff:")
