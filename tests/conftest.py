"""Shared fixtures for the CEN test suite."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from cen.config import Settings
from cen.api.app import create_app


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(llm_backend="mock", log_renderer="console", pii_backend="regex")


@pytest.fixture()
def app(test_settings: Settings):
    return create_app(test_settings)


@pytest.fixture()
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
