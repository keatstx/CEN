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
                "context": {
                    "income_fpl_percent": 150,
                    "patient_name": "Test Patient",
                    "patient_dob": "1980-01-01",
                },
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["module_name"] == "charity_care_navigator"
        assert "intake_start" in data["executed_nodes"]
        # v2 halts at the first APPROVAL gate (hipaa_consent). The gate
        # is *pending*, not executed — it shows up as pending_node.
        assert data["pending_node"] == "hipaa_consent"
        assert "hipaa_consent" not in data["executed_nodes"]
        assert data["final_outcome"].startswith("pending_approval:")

    async def test_execute_missing_module(self, client: AsyncClient):
        resp = await client.post(
            "/execute",
            json={"module_name": "nonexistent", "context": {}},
        )
        assert resp.status_code == 404

    async def test_execute_false_branch(self, client: AsyncClient):
        # With consent granted, the workflow advances past hipaa_consent
        # to the next APPROVAL gate (counselor_qa). Higher FPL routes
        # through fpl_tier_check rather than presumptive eligibility.
        resp = await client.post(
            "/execute",
            json={
                "module_name": "charity_care_navigator",
                "context": {
                    "income_fpl_percent": 300,
                    "consent_granted": True,
                    "documents_complete": True,
                    "presumptive_eligible": False,
                    "hospital_full_writeoff_threshold": 200,
                    "hospital_partial_threshold": 400,
                    "patient_name": "Test Patient",
                    "patient_dob": "1980-01-01",
                },
            },
            params={"session_id": (await client.post(
                "/sessions", json={"module_name": "charity_care_navigator"}
            )).json()["id"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "intake_start" in data["executed_nodes"]
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
