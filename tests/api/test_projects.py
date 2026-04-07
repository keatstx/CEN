"""Tests for /projects CRUD endpoints + auto-default-project on session create."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestProjectCRUD:
    async def test_create_project(self, client: AsyncClient):
        resp = await client.post(
            "/projects",
            json={"name": "Mrs. Jones", "description": "Medical debt + appeal"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Mrs. Jones"
        assert data["description"] == "Medical debt + appeal"
        assert "id" in data

    async def test_get_project(self, client: AsyncClient):
        create = await client.post("/projects", json={"name": "Test"})
        pid = create.json()["id"]
        resp = await client.get(f"/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    async def test_get_nonexistent(self, client: AsyncClient):
        resp = await client.get("/projects/does_not_exist")
        assert resp.status_code == 404

    async def test_list_projects(self, client: AsyncClient):
        await client.post("/projects", json={"name": "A"})
        await client.post("/projects", json={"name": "B"})
        resp = await client.get("/projects")
        assert resp.status_code == 200
        # At least the 2 we just created (plus possibly an auto-default).
        assert len(resp.json()) >= 2

    async def test_update_project(self, client: AsyncClient):
        create = await client.post("/projects", json={"name": "Original"})
        pid = create.json()["id"]
        resp = await client.patch(
            f"/projects/{pid}", json={"name": "Renamed", "description": "Updated"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"
        assert resp.json()["description"] == "Updated"

    async def test_update_nonexistent(self, client: AsyncClient):
        resp = await client.patch("/projects/nope", json={"name": "x"})
        assert resp.status_code == 404

    async def test_delete_project(self, client: AsyncClient):
        create = await client.post("/projects", json={"name": "Disposable"})
        pid = create.json()["id"]
        resp = await client.delete(f"/projects/{pid}")
        assert resp.status_code == 204
        assert (await client.get(f"/projects/{pid}")).status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient):
        resp = await client.delete("/projects/nope")
        assert resp.status_code == 404


class TestSessionAutoDefaultProject:
    async def test_session_without_project_id_gets_default(
        self, client: AsyncClient
    ):
        resp = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] is not None
        # The auto-created default project should now be queryable.
        get_resp = await client.get(f"/projects/{data['project_id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Default"

    async def test_session_with_explicit_project_id(self, client: AsyncClient):
        proj = await client.post("/projects", json={"name": "Explicit"})
        pid = proj.json()["id"]
        sess = await client.post(
            "/sessions",
            json={"module_name": "charity_care_navigator", "project_id": pid},
        )
        assert sess.status_code == 201
        assert sess.json()["project_id"] == pid

    async def test_session_with_explicit_name(self, client: AsyncClient):
        sess = await client.post(
            "/sessions",
            json={
                "module_name": "charity_care_navigator",
                "name": "Mrs. Jones — UHC denial",
            },
        )
        assert sess.status_code == 201
        assert sess.json()["name"] == "Mrs. Jones — UHC denial"

    async def test_session_module_version_pinned(self, client: AsyncClient):
        sess = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        assert sess.status_code == 201
        # Should be a version string (default "1.0" or whatever the AOP declares).
        assert isinstance(sess.json()["module_version"], str)
        assert len(sess.json()["module_version"]) > 0

    async def test_list_sessions_filtered_by_project(self, client: AsyncClient):
        proj_a = (await client.post("/projects", json={"name": "A"})).json()["id"]
        proj_b = (await client.post("/projects", json={"name": "B"})).json()["id"]
        await client.post(
            "/sessions",
            json={"module_name": "charity_care_navigator", "project_id": proj_a},
        )
        await client.post(
            "/sessions",
            json={"module_name": "charity_care_navigator", "project_id": proj_b},
        )
        resp = await client.get("/sessions", params={"project_id": proj_a})
        assert resp.status_code == 200
        assert all(s["project_id"] == proj_a for s in resp.json())
