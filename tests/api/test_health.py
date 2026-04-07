"""Tests for health and readiness routes."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from cen.api.app import create_app
from cen.config import Settings


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_ready(client: AsyncClient):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "charity_care_navigator" in data["modules_loaded"]
    assert data["llm_backend"] == "mock-tlm-v1"
    assert data["llm_available"] is True
    assert data["deployment_mode"] == "synthetic"


class TestDeploymentModeGuard:
    def test_synthetic_mode_with_api_backend_starts_fine(self):
        settings = Settings(
            deployment_mode="synthetic",
            llm_backend="api",
            llm_baa_confirmed=False,
            db_path=":memory:",
        )
        # Should not raise — synthetic mode places no restrictions.
        app = create_app(settings)
        assert app is not None

    def test_production_mode_with_mock_backend_starts_fine(self):
        settings = Settings(
            deployment_mode="production",
            llm_backend="mock",
            db_path=":memory:",
        )
        app = create_app(settings)
        assert app is not None

    def test_production_mode_with_api_backend_no_baa_refuses_to_start(self):
        settings = Settings(
            deployment_mode="production",
            llm_backend="api",
            llm_baa_confirmed=False,
            db_path=":memory:",
        )
        with pytest.raises(RuntimeError, match="CEN_LLM_BAA_CONFIRMED"):
            create_app(settings)

    def test_production_mode_with_api_backend_baa_confirmed_starts_fine(self):
        settings = Settings(
            deployment_mode="production",
            llm_backend="api",
            llm_baa_confirmed=True,
            db_path=":memory:",
        )
        app = create_app(settings)
        assert app is not None
