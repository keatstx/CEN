"""Tests for the v1 auth stub."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.api.app import create_app
from cen.api.dependencies import get_audit_store, get_project_store, get_session_store
from cen.config import Settings


@pytest.fixture()
def auth_settings() -> Settings:
    return Settings(
        llm_backend="mock",
        log_renderer="console",
        pii_backend="regex",
        db_path=":memory:",
        operator_password="hunter2",
    )


@pytest.fixture()
async def auth_client(auth_settings: Settings) -> AsyncClient:
    app = create_app(auth_settings)
    await get_session_store().initialize()
    await get_project_store().initialize()
    await get_audit_store().initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await get_audit_store().close()
    await get_project_store().close()
    await get_session_store().close()


class TestAuthDisabled:
    """When operator_password is empty (default), auth is disabled and
    every request returns the stub default operator. The standard
    `client` fixture from conftest uses this mode."""

    async def test_unauthenticated_session_create_works(self, client: AsyncClient):
        # No Authorization header, no problem.
        resp = await client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        assert resp.status_code == 201
        # owner_id should be the stub default operator id.
        assert resp.json()["owner_id"] == "default-operator"

    async def test_login_returns_no_op_token_when_disabled(
        self, client: AsyncClient
    ):
        resp = await client.post("/auth/login", json={"password": "anything"})
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "dev-no-auth"


class TestAuthEnabled:
    """When operator_password is set, requests must include
    `Authorization: Bearer <password>`."""

    async def test_login_success(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/login", json={"password": "hunter2"}
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "hunter2"
        assert resp.json()["token_type"] == "bearer"

    async def test_login_wrong_password(self, auth_client: AsyncClient):
        resp = await auth_client.post(
            "/auth/login", json={"password": "wrong"}
        )
        assert resp.status_code == 401

    async def test_protected_route_without_token_rejected(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post(
            "/sessions", json={"module_name": "charity_care_navigator"}
        )
        assert resp.status_code == 401

    async def test_protected_route_with_wrong_token_rejected(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post(
            "/sessions",
            json={"module_name": "charity_care_navigator"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401

    async def test_protected_route_with_malformed_header_rejected(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post(
            "/sessions",
            json={"module_name": "charity_care_navigator"},
            headers={"Authorization": "Token hunter2"},
        )
        assert resp.status_code == 401

    async def test_protected_route_with_valid_token_works(
        self, auth_client: AsyncClient
    ):
        resp = await auth_client.post(
            "/sessions",
            json={"module_name": "charity_care_navigator"},
            headers={"Authorization": "Bearer hunter2"},
        )
        assert resp.status_code == 201
        assert resp.json()["owner_id"] == "default-operator"

    async def test_projects_create_protected(self, auth_client: AsyncClient):
        # Without token: 401
        resp = await auth_client.post("/projects", json={"name": "x"})
        assert resp.status_code == 401
        # With token: 201
        resp = await auth_client.post(
            "/projects",
            json={"name": "x"},
            headers={"Authorization": "Bearer hunter2"},
        )
        assert resp.status_code == 201
        assert resp.json()["owner_id"] == "default-operator"
