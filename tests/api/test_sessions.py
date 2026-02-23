"""Tests for session CRUD and /execute session integration."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestSessionCRUD:
    async def test_create_session(self, client: AsyncClient):
        resp = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["module_name"] == "charity_care_navigator"
        assert data["status"] == "ACTIVE"
        assert "id" in data

    async def test_create_invalid_module(self, client: AsyncClient):
        resp = await client.post(
            "/sessions", json={"module_name": "nonexistent"}
        )
        assert resp.status_code == 404

    async def test_get_session(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        resp = await client.get(f"/sessions/{sid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sid

    async def test_get_nonexistent(self, client: AsyncClient):
        resp = await client.get("/sessions/does_not_exist")
        assert resp.status_code == 404

    async def test_list_sessions(self, client: AsyncClient):
        await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_with_filter(self, client: AsyncClient):
        await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        resp = await client.get("/sessions", params={"module_name": "charity_care_navigator"})
        assert resp.status_code == 200
        assert all(s["module_name"] == "charity_care_navigator" for s in resp.json())

    async def test_update_session(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        resp = await client.patch(
            f"/sessions/{sid}", json={"status": "COMPLETED"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "COMPLETED"

    async def test_delete_session(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        resp = await client.delete(f"/sessions/{sid}")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"/sessions/{sid}")
        assert resp2.status_code == 404


class TestExecuteWithSession:
    async def test_execute_persists_context(self, client: AsyncClient):
        # Create session
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]

        # Execute with session
        resp = await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        assert resp.status_code == 200

        # Verify session was updated — stops at approval gate
        session = await client.get(f"/sessions/{sid}")
        data = session.json()
        assert data["status"] == "AWAITING_APPROVAL"
        assert len(data["executed_nodes"]) > 0
        assert "income_fpl_percent" in data["context"]

    async def test_execute_merges_context(self, client: AsyncClient):
        # Create session with initial context
        create = await client.post(
            "/sessions",
            json={
                "module_name": "charity_care_navigator",
                "context": {"saved_key": "saved_value", "income_fpl_percent": 999},
            },
        )
        sid = create.json()["id"]

        # Execute — incoming context should override saved
        resp = await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        assert resp.status_code == 200
        result = resp.json()
        # Incoming 150 should have overridden saved 999
        assert result["context"]["income_fpl_percent"] == 150

    async def test_execute_nonexistent_session(self, client: AsyncClient):
        resp = await client.post(
            "/execute",
            params={"session_id": "does_not_exist"},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        assert resp.status_code == 404

    async def test_execute_without_session_unchanged(self, client: AsyncClient):
        # No session_id — should work exactly as before
        resp = await client.post(
            "/execute",
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["module_name"] == "charity_care_navigator"


class TestApprovalFlow:
    async def test_full_approval_lifecycle(self, client: AsyncClient):
        # Create session
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]

        # Execute — should stop at counselor_approval
        resp = await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["final_outcome"].startswith("pending_approval:")
        assert "counselor_approval" in data["executed_nodes"]
        assert "handoff_counselor" not in data["executed_nodes"]

        # Verify session is AWAITING_APPROVAL
        session_resp = await client.get(f"/sessions/{sid}")
        session_data = session_resp.json()
        assert session_data["status"] == "AWAITING_APPROVAL"
        assert session_data["pending_node"] == "counselor_approval"

        # Approve
        approve_resp = await client.post(f"/sessions/{sid}/approve")
        assert approve_resp.status_code == 200
        approve_data = approve_resp.json()
        assert approve_data["final_outcome"].startswith("handoff:")
        assert "handoff_counselor" in approve_data["executed_nodes"]

        # Verify session is now COMPLETED
        final = await client.get(f"/sessions/{sid}")
        final_data = final.json()
        assert final_data["status"] == "COMPLETED"
        assert "counselor_approval" in final_data["approved_nodes"]

    async def test_approve_non_awaiting_session_returns_409(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        # Session is ACTIVE, not AWAITING_APPROVAL
        resp = await client.post(f"/sessions/{sid}/approve")
        assert resp.status_code == 409

    async def test_approve_nonexistent_session_returns_404(self, client: AsyncClient):
        resp = await client.post("/sessions/does_not_exist/approve")
        assert resp.status_code == 404


class TestAuditTrail:
    async def test_audit_after_execute(self, client: AsyncClient):
        # Create session and execute workflow
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )

        # Fetch audit trail
        resp = await client.get(f"/sessions/{sid}/audit")
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) > 0
        # Each entry should have the expected fields
        for entry in entries:
            assert "id" in entry
            assert entry["session_id"] == sid
            assert "module" in entry
            assert "node_id" in entry
            assert "node_type" in entry
            assert "outcome" in entry
            assert "context" in entry
            assert "timestamp" in entry

    async def test_audit_per_node_granularity(self, client: AsyncClient):
        # Create session and execute workflow
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        exec_resp = await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        executed_nodes = exec_resp.json()["executed_nodes"]

        # Audit trail should have one entry per executed node
        resp = await client.get(f"/sessions/{sid}/audit")
        audit_entries = resp.json()
        audit_node_ids = [e["node_id"] for e in audit_entries]
        assert audit_node_ids == executed_nodes

    async def test_audit_nonexistent_session_returns_404(self, client: AsyncClient):
        resp = await client.get("/sessions/does_not_exist/audit")
        assert resp.status_code == 404

    async def test_full_approval_audit_trail(self, client: AsyncClient):
        # Create session
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]

        # Execute — should stop at approval gate
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )

        # Approve
        await client.post(f"/sessions/{sid}/approve")

        # Audit trail should include approval event and subsequent nodes
        resp = await client.get(f"/sessions/{sid}/audit")
        entries = resp.json()
        outcomes = [e["outcome"] for e in entries]
        node_ids = [e["node_id"] for e in entries]

        # Should have the pending_approval from initial execute
        assert "pending_approval" in outcomes
        # Should have the explicit approval event
        assert "approved" in outcomes
        # Should have handoff from re-execution after approval
        assert any(o.startswith("handoff:") for o in outcomes)
        # The approval node should appear in the trail
        assert "counselor_approval" in node_ids

    async def test_audit_filter_by_node_type(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        # Filter to only APPROVAL type
        resp = await client.get(f"/sessions/{sid}/audit", params={"node_type": "APPROVAL"})
        assert resp.status_code == 200
        entries = resp.json()
        assert all(e["node_type"] == "APPROVAL" for e in entries)

    async def test_audit_pagination(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        # Paginate
        resp = await client.get(f"/sessions/{sid}/audit", params={"limit": 1, "offset": 0})
        assert resp.status_code == 200
        page1 = resp.json()
        assert len(page1) == 1

        resp2 = await client.get(f"/sessions/{sid}/audit", params={"limit": 1, "offset": 1})
        page2 = resp2.json()
        assert len(page2) == 1
        assert page1[0]["id"] != page2[0]["id"]

    async def test_audit_entries_have_record_hash(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        resp = await client.get(f"/sessions/{sid}/audit")
        entries = resp.json()
        for entry in entries:
            assert "record_hash" in entry
            assert len(entry["record_hash"]) == 64


class TestAuditVerify:
    async def test_verify_valid_chain(self, client: AsyncClient):
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        resp = await client.get(f"/sessions/{sid}/audit/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["total_records"] > 0
        assert data["last_verified_id"] > 0
        assert "verified_at" in data

    async def test_verify_nonexistent_session_returns_404(self, client: AsyncClient):
        resp = await client.get("/sessions/does_not_exist/audit/verify")
        assert resp.status_code == 404


class TestAuditExport:
    async def _create_and_execute(self, client: AsyncClient) -> str:
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        await client.post(
            "/execute",
            params={"session_id": sid},
            json={
                "module_name": "charity_care_navigator",
                "context": {"income_fpl_percent": 150},
            },
        )
        return sid

    async def test_export_json(self, client: AsyncClient):
        sid = await self._create_and_execute(client)
        resp = await client.get(f"/sessions/{sid}/audit/export", params={"format": "json"})
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_export_csv(self, client: AsyncClient):
        sid = await self._create_and_execute(client)
        resp = await client.get(f"/sessions/{sid}/audit/export", params={"format": "csv"})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "attachment" in resp.headers["content-disposition"]
        lines = resp.text.strip().split("\n")
        assert len(lines) > 1  # Header + data rows

    async def test_export_default_is_json(self, client: AsyncClient):
        sid = await self._create_and_execute(client)
        resp = await client.get(f"/sessions/{sid}/audit/export")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    async def test_export_nonexistent_session_returns_404(self, client: AsyncClient):
        resp = await client.get("/sessions/does_not_exist/audit/export")
        assert resp.status_code == 404

    async def test_export_with_filters(self, client: AsyncClient):
        sid = await self._create_and_execute(client)
        resp = await client.get(
            f"/sessions/{sid}/audit/export",
            params={"format": "json", "node_type": "ACTION"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["node_type"] == "ACTION" for e in data)
