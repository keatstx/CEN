"""Tests for the /me current-user endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.api.app import create_app
from cen.api.dependencies import get_audit_store, get_project_store, get_session_store
from cen.config import Settings


class TestMeStubMode:
    """When auth is disabled, /me returns the dev stub user with is_admin=True."""

    async def test_me_returns_stub_user(self, client: AsyncClient):
        resp = await client.get("/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "default-operator"
        assert body["name"] == "Default Operator"
        assert body["is_admin"] is True


class TestMePasswordAuth:
    """When auth is enabled, /me requires the bearer token and honors
    CEN_ADMIN_OPERATORS for the admin flag."""

    @pytest.fixture()
    async def admin_client(self) -> AsyncClient:
        settings = Settings(
            llm_backend="mock",
            log_renderer="console",
            pii_backend="regex",
            db_path=":memory:",
            operator_password="hunter2",
            admin_operators=["default-operator"],
        )
        app = create_app(settings)
        await get_session_store().initialize()
        await get_project_store().initialize()
        await get_audit_store().initialize()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        await get_audit_store().close()
        await get_project_store().close()
        await get_session_store().close()

    @pytest.fixture()
    async def non_admin_client(self) -> AsyncClient:
        settings = Settings(
            llm_backend="mock",
            log_renderer="console",
            pii_backend="regex",
            db_path=":memory:",
            operator_password="hunter2",
            admin_operators=[],
        )
        app = create_app(settings)
        await get_session_store().initialize()
        await get_project_store().initialize()
        await get_audit_store().initialize()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        await get_audit_store().close()
        await get_project_store().close()
        await get_session_store().close()

    async def test_me_without_token_rejected(self, admin_client: AsyncClient):
        resp = await admin_client.get("/me")
        assert resp.status_code == 401

    async def test_me_admin_operator_flagged(self, admin_client: AsyncClient):
        resp = await admin_client.get(
            "/me", headers={"Authorization": "Bearer hunter2"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "default-operator"
        assert body["is_admin"] is True

    async def test_me_non_admin_not_flagged(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.get(
            "/me", headers={"Authorization": "Bearer hunter2"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "default-operator"
        assert body["is_admin"] is False
