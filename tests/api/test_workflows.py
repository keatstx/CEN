"""Tests for workflow API routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestExecuteEndpoint:
    async def test_execute_charity_care(self, client: AsyncClient):
        resp = await client.post(
            "/execute",
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["module_name"] == "charity_care_navigator"
        assert "auto_app" in data["executed_nodes"]
        assert "debt_cancellation" not in data["executed_nodes"]
        # Stops at approval gate instead of reaching handoff
        assert "counselor_approval" in data["executed_nodes"]
        assert data["final_outcome"].startswith("pending_approval:")

    async def test_execute_missing_module(self, client: AsyncClient):
        resp = await client.post(
            "/execute",
            json={"module_name": "nonexistent", "context": {}},
        )
        assert resp.status_code == 404

    async def test_execute_false_branch(self, client: AsyncClient):
        resp = await client.post(
            "/execute",
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 300},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "debt_cancellation" in data["executed_nodes"]
        assert "auto_app" not in data["executed_nodes"]
        # Stops at approval gate
        assert "counselor_approval" in data["executed_nodes"]
        assert data["final_outcome"].startswith("pending_approval:")


class TestUpdateAOP:
    async def test_update_aop(self, client: AsyncClient):
        resp = await client.post(
            "/update-aop",
            json={
                "module_name": "dynamic_test",
                "nodes": [
                    {"id": "start", "type": "ACTION"},
                    {"id": "end", "type": "HANDOFF"},
                ],
                "edges": [{"source": "start", "target": "end"}],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Now execute it
        resp2 = await client.post(
            "/execute",
            json={"module_name": "dynamic_test", "context": {}},
        )
        assert resp2.status_code == 200

    async def test_update_aop_rejects_cycle(self, client: AsyncClient):
        resp = await client.post(
            "/update-aop",
            json={
                "module_name": "cyclic",
                "nodes": [
                    {"id": "a", "type": "ACTION"},
                    {"id": "b", "type": "ACTION"},
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                    {"source": "b", "target": "a"},
                ],
            },
        )
        assert resp.status_code == 400
