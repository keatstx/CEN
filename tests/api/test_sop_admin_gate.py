"""Tests for the admin gate on /sop/* routes.

Non-admin operators must receive 403 on every SOP route. Admin operators
(default in dev stub) keep access.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.api.app import create_app
from cen.api.dependencies import (
    get_audit_store,
    get_chat_store,
    get_faq_store,
    get_project_store,
    get_session_store,
    get_sop_store,
)
from cen.config import Settings


@pytest.fixture()
async def non_admin_client(tmp_path) -> AsyncClient:
    settings = Settings(
        llm_backend="mock",
        log_renderer="console",
        pii_backend="regex",
        db_path=":memory:",
        uploads_dir=str(tmp_path / "uploads"),
        operator_password="hunter2",
        admin_operators=[],  # nobody is admin
    )
    app = create_app(settings)
    await get_session_store().initialize()
    await get_project_store().initialize()
    await get_audit_store().initialize()
    await get_faq_store().initialize()
    await get_chat_store().initialize()
    await get_sop_store().initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await get_sop_store().close()
    await get_chat_store().close()
    await get_faq_store().close()
    await get_audit_store().close()
    await get_project_store().close()
    await get_session_store().close()


class TestSopRoutesGatedForNonAdmin:
    """Every /sop/* route should 403 a non-admin user."""

    AUTH = {"Authorization": "Bearer hunter2"}
    DUMMY_ID = "00000000-0000-0000-0000-000000000000"

    async def test_list_sops_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.get("/sop", headers=self.AUTH)
        assert resp.status_code == 403

    async def test_upload_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.post(
            "/sop/upload",
            headers=self.AUTH,
            files={"file": ("test.md", b"# SOP", "text/markdown")},
        )
        assert resp.status_code == 403

    async def test_get_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.get(
            f"/sop/{self.DUMMY_ID}", headers=self.AUTH
        )
        assert resp.status_code == 403

    async def test_parse_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.post(
            f"/sop/{self.DUMMY_ID}/parse", headers=self.AUTH
        )
        assert resp.status_code == 403

    async def test_extract_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.post(
            f"/sop/{self.DUMMY_ID}/extract", headers=self.AUTH
        )
        assert resp.status_code == 403

    async def test_apply_fix_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.post(
            f"/sop/{self.DUMMY_ID}/apply_fix",
            headers=self.AUTH,
            json={"issue_id": "x", "fix_id": "y"},
        )
        assert resp.status_code == 403

    async def test_auto_fix_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.post(
            f"/sop/{self.DUMMY_ID}/auto_fix", headers=self.AUTH
        )
        assert resp.status_code == 403

    async def test_promote_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.post(
            f"/sop/{self.DUMMY_ID}/promote", headers=self.AUTH
        )
        assert resp.status_code == 403

    async def test_delete_forbidden(self, non_admin_client: AsyncClient):
        resp = await non_admin_client.delete(
            f"/sop/{self.DUMMY_ID}", headers=self.AUTH
        )
        assert resp.status_code == 403


class TestSopRoutesOpenForAdmin:
    """Dev stub user is admin by default — original SOP test coverage
    continues to pass via the standard `client` fixture. We just sanity-
    check that /sop responds (not 403) under the stub."""

    async def test_list_sops_ok_as_admin(self, client: AsyncClient):
        resp = await client.get("/sop")
        assert resp.status_code == 200
