"""Tests for the /cases/{id}/resume_external endpoint.

Covers the AWAITING_EXTERNAL lifecycle: a HANDOFF with
``pause_on_handoff: true`` pauses the case, the resume endpoint
advances it past the handoff, and a 409 is returned when the case
isn't actually waiting on external input.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cen.core.models import (
    AOPDefinition,
    AOPEdge,
    AOPNode,
    NodeMetadata,
    NodeType,
)


def _pause_handoff_aop_dict() -> dict:
    """An AOP with one ACTION followed by a paused HANDOFF.

    Built as a dict so it round-trips through the /update-aop route
    cleanly. We register it on the live engine so a real case can be
    created against it.
    """
    return AOPDefinition(
        module_name="pause_handoff_test",
        nodes=[
            AOPNode(
                id="intake",
                type=NodeType.ACTION,
                metadata=NodeMetadata(label="Intake"),
            ),
            AOPNode(
                id="hospital",
                type=NodeType.HANDOFF,
                metadata=NodeMetadata(
                    label="Send to hospital",
                    params={"pause_on_handoff": True},
                ),
            ),
        ],
        edges=[AOPEdge(source="intake", target="hospital")],
    ).model_dump()


@pytest.mark.asyncio
async def test_resume_external_lifecycle(client):
    # Register the test module on the live engine via /update-aop.
    r = await client.post("/update-aop", json=_pause_handoff_aop_dict())
    assert r.status_code == 200, r.text

    # Create a case + execute → workflow should pause at the HANDOFF.
    create = await client.post(
        "/cases", json={"module_name": "pause_handoff_test"}
    )
    cid = create.json()["id"]
    exec_resp = await client.post(
        "/execute",
        params={"session_id": cid},
        json={"module_name": "pause_handoff_test", "context": {}},
    )
    assert exec_resp.status_code == 200, exec_resp.text
    assert exec_resp.json()["final_outcome"].startswith("awaiting_external:")

    # Case should now be AWAITING_EXTERNAL.
    case = (await client.get(f"/cases/{cid}")).json()
    assert case["status"] == "AWAITING_EXTERNAL"
    assert case["pending_node"] == "hospital"

    # Resume — workflow advances past the handoff and completes.
    resume = await client.post(f"/cases/{cid}/resume_external")
    assert resume.status_code == 200, resume.text

    case_after = (await client.get(f"/cases/{cid}")).json()
    assert case_after["status"] == "COMPLETED"
    assert case_after["pending_node"] is None


@pytest.mark.asyncio
async def test_resume_external_refuses_when_not_waiting(client):
    """A freshly-created ACTIVE case can't be 'resumed external'."""
    r = await client.post("/cases", json={"module_name": "charity_care_navigator"})
    cid = r.json()["id"]

    resp = await client.post(f"/cases/{cid}/resume_external")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_resume_external_404_for_unknown_case(client):
    resp = await client.post("/cases/nonexistent/resume_external")
    assert resp.status_code == 404
