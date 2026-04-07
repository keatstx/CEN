"""Shared fixtures for the CEN test suite."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.config import Settings
from cen.api.app import create_app
from cen.api.dependencies import (
    get_artifact_store,
    get_audit_store,
    get_faq_store,
    get_project_store,
    get_session_store,
)


@pytest.fixture()
def test_settings(tmp_path) -> Settings:
    return Settings(
        llm_backend="mock",
        log_renderer="console",
        pii_backend="regex",
        db_path=":memory:",
        uploads_dir=str(tmp_path / "uploads"),
    )


@pytest.fixture()
def app(test_settings: Settings):
    return create_app(test_settings)


@pytest.fixture()
async def client(app) -> AsyncClient:
    # Manually initialize the stores (lifespan doesn't run in test transport)
    store = get_session_store()
    await store.initialize()
    project_store = get_project_store()
    await project_store.initialize()
    audit_store = get_audit_store()
    await audit_store.initialize()
    artifact_store = get_artifact_store()
    await artifact_store.initialize()
    faq_store = get_faq_store()
    await faq_store.initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await faq_store.close()
    await artifact_store.close()
    await audit_store.close()
    await project_store.close()
    await store.close()
