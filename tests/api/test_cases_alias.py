"""Tests confirming /cases is a working alias for /sessions.

Per CLAUDE.md §7, the codebase is migrating from "session" to "case"
terminology. This commit lands the route alias so the frontend can
migrate at its own pace. Both /sessions/* and /cases/* hit the same
handler functions and the same store — there is no data divergence.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestCasesAlias:
    async def test_cases_create_and_get(self, client: AsyncClient):
        resp = await client.post(
            "/cases", json={"module_name": "charity_care_navigator"}
        )
        assert resp.status_code == 201
        cid = resp.json()["id"]
        # GET via /cases works.
        get_resp = await client.get(f"/cases/{cid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == cid

    async def test_case_visible_via_sessions_alias(self, client: AsyncClient):
        # Create via /cases, fetch via /sessions — same store, same row.
        create = await client.post(
            "/cases", json={"module_name": "charity_care_navigator"}
        )
        cid = create.json()["id"]
        get_resp = await client.get(f"/sessions/{cid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == cid

    async def test_session_visible_via_cases_alias(self, client: AsyncClient):
        # Create via /sessions, fetch via /cases — same store, same row.
        create = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        sid = create.json()["id"]
        get_resp = await client.get(f"/cases/{sid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == sid

    async def test_cases_list_includes_session_creates(self, client: AsyncClient):
        # Create some via each path.
        await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        await client.post(
            "/cases", json={"module_name": "charity_care_navigator"}
        )
        # /cases list should see both.
        resp = await client.get("/cases")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    async def test_cases_patch_works(self, client: AsyncClient):
        create = await client.post(
            "/cases",
            json={
                "module_name": "charity_care_navigator",
                "name": "Original",
            },
        )
        cid = create.json()["id"]
        # PATCH via /cases — note /sessions and /cases share the
        # same SessionUpdate model.
        resp = await client.patch(
            f"/cases/{cid}", json={"context": {"updated": True}}
        )
        assert resp.status_code == 200
        assert resp.json()["context"] == {"updated": True}

    async def test_cases_delete_works(self, client: AsyncClient):
        create = await client.post(
            "/cases", json={"module_name": "charity_care_navigator"}
        )
        cid = create.json()["id"]
        resp = await client.delete(f"/cases/{cid}")
        assert resp.status_code == 204
        # Confirm gone via the legacy path too.
        get_resp = await client.get(f"/sessions/{cid}")
        assert get_resp.status_code == 404
