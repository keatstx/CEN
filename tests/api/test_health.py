"""Tests for health and readiness routes."""

from __future__ import annotations

from httpx import AsyncClient


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
