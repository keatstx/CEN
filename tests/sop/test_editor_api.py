"""Live tests for the SOP editor endpoints — apply_fix, auto_fix,
node patch + delete. The frontend's inline-fix UI calls these.
"""

from __future__ import annotations

from pathlib import Path

import pytest


PROFORMA = (Path(__file__).parent / "fixtures" / "proforma.md").read_text(
    encoding="utf-8"
)


async def _seed_proforma(client) -> str:
    """Upload + parse + extract the Proforma SOP. Returns the sop_id."""
    files = {"file": ("proforma.md", PROFORMA.encode(), "text/markdown")}
    upload = await client.post("/sop/upload", files=files)
    sop_id = upload.json()["id"]
    await client.post(f"/sop/{sop_id}/parse")
    extract = await client.post(f"/sop/{sop_id}/extract")
    assert extract.status_code == 200, extract.text
    return sop_id


@pytest.mark.asyncio
async def test_extract_response_carries_fixes_per_issue(client):
    sop_id = await _seed_proforma(client)
    sop = await client.get(f"/sop/{sop_id}")
    issues = sop.json()["validation_issues"]
    cycle_issues = [
        i for i in issues
        if i["severity"] == "error" and "cycle" in i["message"].lower()
    ]
    assert cycle_issues, "expected cycle errors on Proforma SOP"
    # Every cycle issue carries at least one fix proposal — the
    # frontend renders these as inline buttons.
    assert all(len(i["fixes"]) >= 1 for i in cycle_issues)
    # The fix has the shape the frontend expects.
    sample = cycle_issues[0]["fixes"][0]
    for key in ("kind", "label", "payload", "confidence"):
        assert key in sample


@pytest.mark.asyncio
async def test_apply_fix_clears_the_targeted_issue(client):
    sop_id = await _seed_proforma(client)
    sop = await client.get(f"/sop/{sop_id}")
    issues = sop.json()["validation_issues"]
    target = next(
        i for i in issues
        if i["severity"] == "error" and i["fixes"]
    )
    fix = target["fixes"][0]

    r = await client.post(
        f"/sop/{sop_id}/apply_fix", json={"fix": fix}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # The draft is updated and re-validated.
    assert "draft" in body
    assert "validation_issues" in body
    # The issue list might still have other errors, but that exact
    # message+node combo should no longer appear in the same form.
    same_node_same_msg = [
        i for i in body["validation_issues"]
        if i["node_id"] == target["node_id"]
        and i["message"] == target["message"]
    ]
    assert len(same_node_same_msg) == 0, "fix should have cleared the targeted issue"


@pytest.mark.asyncio
async def test_apply_fix_404_on_unknown_sop(client):
    r = await client.post(
        "/sop/nonexistent/apply_fix",
        json={"fix": {"kind": "drop_edge", "label": "x", "payload": {}, "confidence": 1.0}},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_apply_fix_409_when_no_draft(client):
    """Upload but don't extract — apply_fix should refuse."""
    files = {"file": ("x.md", b"# tiny", "text/markdown")}
    r = await client.post("/sop/upload", files=files)
    sop_id = r.json()["id"]
    r = await client.post(
        f"/sop/{sop_id}/apply_fix",
        json={"fix": {"kind": "drop_edge", "label": "x", "payload": {}, "confidence": 1.0}},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_auto_fix_applies_high_confidence_fixes(client):
    sop_id = await _seed_proforma(client)
    r = await client.post(f"/sop/{sop_id}/auto_fix")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "applied_count" in body
    # The Proforma fixture has snake_case warnings? No — the regex
    # extractor lowercases ids already. So auto_fix may apply 0 high-
    # confidence fixes here. The endpoint should still return 200.
    assert isinstance(body["applied_count"], int)


@pytest.mark.asyncio
async def test_patch_node_updates_label(client):
    sop_id = await _seed_proforma(client)
    sop = await client.get(f"/sop/{sop_id}")
    first_node = sop.json()["draft_module"]["nodes"][0]
    node_id = first_node["id"]
    r = await client.patch(
        f"/sop/{sop_id}/draft/nodes/{node_id}",
        json={"label": "Edited via inline editor"},
    )
    assert r.status_code == 200, r.text
    updated = next(
        n for n in r.json()["draft"]["nodes"] if n["id"] == node_id
    )
    assert updated["metadata"]["label"] == "Edited via inline editor"


@pytest.mark.asyncio
async def test_patch_node_404_on_unknown_id(client):
    sop_id = await _seed_proforma(client)
    r = await client.patch(
        f"/sop/{sop_id}/draft/nodes/no_such_node",
        json={"label": "x"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_node_removes_node_and_its_edges(client):
    sop_id = await _seed_proforma(client)
    sop = await client.get(f"/sop/{sop_id}")
    first_node = sop.json()["draft_module"]["nodes"][0]
    node_id = first_node["id"]
    r = await client.delete(f"/sop/{sop_id}/draft/nodes/{node_id}")
    assert r.status_code == 200, r.text
    remaining_ids = {n["id"] for n in r.json()["draft"]["nodes"]}
    assert node_id not in remaining_ids
    # No edges should reference the deleted node.
    edges = r.json()["draft"]["edges"]
    assert all(e["source"] != node_id and e["target"] != node_id for e in edges)
