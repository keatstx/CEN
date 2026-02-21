"""Shared fixtures for the CEN test suite."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.config import Settings
from cen.api.app import create_app
from cen.api.dependencies import get_session_store


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(llm_backend="mock", log_renderer="console", pii_backend="regex", db_path=":memory:")


@pytest.fixture()
def app(test_settings: Settings):
    return create_app(test_settings)


@pytest.fixture()
async def client(app) -> AsyncClient:
    # Manually initialize the session store (lifespan doesn't run in test transport)
    store = get_session_store()
    await store.initialize()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await store.close()
