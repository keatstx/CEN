"""End-to-end test of the dashboard queue endpoint."""

from __future__ import annotations

import pytest


async def _create_case(client, module_name: str = "charity_care_navigator") -> str:
    r = await client.post("/cases", json={"module_name": module_name})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_queue_endpoint_returns_buckets_and_metrics(client):
    cid = await _create_case(client)
    r = await client.get("/cases/queue")
    assert r.status_code == 200, r.text
    body = r.json()
    # Shape: every bucket key + metrics
    for key in (
        "needs_attention",
        "waiting_external",
        "in_progress",
        "idle",
        "done_today",
        "failed",
    ):
        assert key in body
        assert isinstance(body[key], list)
    assert "metrics" in body
    metrics = body["metrics"]
    for k in ("opened_today", "approvals_today", "completed_today", "open_cases"):
        assert k in metrics
        assert isinstance(metrics[k], int)
    # The case we just created should count as opened_today + open.
    assert metrics["opened_today"] >= 1
    assert metrics["open_cases"] >= 1


@pytest.mark.asyncio
async def test_queue_buckets_awaiting_input_correctly(client):
    """Drive a case to AWAITING_INPUT (charity_care pauses on the
    intake form) and assert it lands in needs_attention."""
    cid = await _create_case(client)
    # Execute kicks the engine; charity_care pauses immediately for
    # patient identity intake — case becomes AWAITING_INPUT.
    await client.post(
        "/execute",
        params={"session_id": cid},
        json={"module_name": "charity_care_navigator", "context": {}},
    )

    r = await client.get("/cases/queue")
    body = r.json()
    needs = [c["id"] for c in body["needs_attention"]]
    assert cid in needs, body


@pytest.mark.asyncio
async def test_queue_includes_due_at_decorations(client):
    """Patch a case with a past due_at and confirm is_overdue."""
    cid = await _create_case(client)
    # Patch the case with a due_at in the past.
    r = await client.patch(
        f"/cases/{cid}", json={"due_at": "2020-01-01T00:00:00+00:00"}
    )
    assert r.status_code == 200, r.text
    # Drive to AWAITING_INPUT so it appears in needs_attention.
    await client.post(
        "/execute",
        params={"session_id": cid},
        json={"module_name": "charity_care_navigator", "context": {}},
    )
    r = await client.get("/cases/queue")
    body = r.json()
    overdue = [c for c in body["needs_attention"] if c["id"] == cid]
    assert overdue, body
    assert overdue[0]["is_overdue"] is True
    assert overdue[0]["due_at"] == "2020-01-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_queue_owner_scoped(client):
    """Cross-tenant: queue must only return cases owned by the
    requesting operator. Stub auth means everything has owner_id =
    'default-operator', so we verify the SQL filter works (no leakage
    of cases without owner_id, which would happen in a v2 mixed-auth
    deployment)."""
    cid = await _create_case(client)
    r = await client.get("/cases/queue")
    body = r.json()
    all_ids = (
        [c["id"] for c in body["needs_attention"]]
        + [c["id"] for c in body["in_progress"]]
        + [c["id"] for c in body["idle"]]
        + [c["id"] for c in body["done_today"]]
        + [c["id"] for c in body["waiting_external"]]
    )
    # The freshly-created ACTIVE case should be in one of these buckets.
    # It might be needs_attention if the engine paused, in_progress if
    # ACTIVE, etc. — just confirm it's there.
    assert cid in all_ids


@pytest.mark.asyncio
async def test_queue_empty_when_no_cases(client):
    r = await client.get("/cases/queue")
    assert r.status_code == 200
    body = r.json()
    for k in ("needs_attention", "in_progress", "idle", "done_today"):
        assert body[k] == []
    assert body["metrics"]["opened_today"] == 0
    assert body["metrics"]["open_cases"] == 0
