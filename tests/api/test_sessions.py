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

        # Verify session was updated
        session = await client.get(f"/sessions/{sid}")
        data = session.json()
        assert data["status"] != "ACTIVE" or len(data["executed_nodes"]) > 0
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
