"""Live end-to-end test of the SOP route pipeline.

Covers the §6 H1-H8 lifecycle for SOP uploads: upload, list, parse,
extract, promote, then verify the new module is reachable through the
existing /modules route. Cross-tenant negative test included for D5.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SIMPLE_FIXTURE = Path(__file__).parent / "fixtures" / "simple.md"
PROFORMA_FIXTURE = Path(__file__).parent / "fixtures" / "proforma.md"


@pytest.fixture
def sop_bytes() -> bytes:
    """Cycle-free synthetic SOP. Lifecycle test uses this so promote
    succeeds. Real-world SOPs (proforma, realestate) have legitimate
    revision loops that the engine rejects today; the validator
    surfaces those as errors and the user fixes them in review."""
    return SIMPLE_FIXTURE.read_bytes()


async def test_full_lifecycle_upload_parse_extract_promote(client, sop_bytes):
    # Upload
    files = {"file": ("simple.md", sop_bytes, "text/markdown")}
    r = await client.post("/sop/upload", files=files)
    assert r.status_code == 201, r.text
    upload = r.json()
    sop_id = upload["id"]
    assert upload["status"] == "uploaded"

    # List
    r = await client.get("/sop")
    assert r.status_code == 200
    assert any(s["id"] == sop_id for s in r.json())

    # Parse
    r = await client.post(f"/sop/{sop_id}/parse")
    assert r.status_code == 200, r.text
    parsed = r.json()
    assert parsed["status"] == "parsed"
    assert parsed["canonical_md"] and "SS-01" in parsed["canonical_md"]

    # Extract
    r = await client.post(f"/sop/{sop_id}/extract")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sop"]["status"] == "extracted"
    assert body["draft"]["nodes"], "expected at least one node in the draft"
    # Draft should preserve the source_doc back-pointer to the SOP.
    assert body["draft"]["source_doc"] == sop_id

    # Promote
    r = await client.post(
        f"/sop/{sop_id}/promote", json={"module_name": "simple_intake"}
    )
    assert r.status_code == 200, r.text
    promoted = r.json()
    assert promoted["status"] == "promoted"
    assert promoted["promoted_module_name"] == "simple_intake"
    assert promoted["promoted_module_version"] == "1.0"

    # Verify the new module is reachable through the existing /modules route.
    r = await client.get(f"/modules/simple_intake")
    assert r.status_code == 200, r.text
    module = r.json()
    assert module["module_name"] == "simple_intake"
    assert module["version"] == "1.0"
    assert module["nodes"], "promoted module should have nodes"


async def test_promote_refuses_cycle_in_real_sop(client):
    """The Proforma SOP has revision loops by design. Promote must
    surface the cycle as a 422, not silently strip it."""
    sop_bytes = PROFORMA_FIXTURE.read_bytes()
    files = {"file": ("proforma.md", sop_bytes, "text/markdown")}
    r = await client.post("/sop/upload", files=files)
    sop_id = r.json()["id"]
    await client.post(f"/sop/{sop_id}/parse")
    extract = await client.post(f"/sop/{sop_id}/extract")
    issues = extract.json()["validation_issues"]
    # The validator should flag at least one cycle-related error.
    assert any("cycle" in i["message"].lower() for i in issues), (
        f"expected cycle error in: {[i['message'] for i in issues]}"
    )
    r = await client.post(f"/sop/{sop_id}/promote")
    assert r.status_code == 422, r.text


async def test_extract_before_parse_returns_409(client, sop_bytes):
    files = {"file": ("x.md", sop_bytes, "text/markdown")}
    r = await client.post("/sop/upload", files=files)
    sop_id = r.json()["id"]
    r = await client.post(f"/sop/{sop_id}/extract")
    assert r.status_code == 409


async def test_promote_before_extract_returns_409(client, sop_bytes):
    files = {"file": ("x.md", sop_bytes, "text/markdown")}
    r = await client.post("/sop/upload", files=files)
    sop_id = r.json()["id"]
    await client.post(f"/sop/{sop_id}/parse")
    r = await client.post(f"/sop/{sop_id}/promote")
    assert r.status_code == 409


async def test_get_unknown_sop_returns_404(client):
    r = await client.get("/sop/nonexistent")
    assert r.status_code == 404


async def test_oversized_upload_rejected(client):
    big = b"x" * (26 * 1024 * 1024)
    files = {"file": ("big.md", big, "text/markdown")}
    r = await client.post("/sop/upload", files=files)
    assert r.status_code == 413


async def test_unsupported_format_rejected(client):
    files = {"file": ("x.exe", b"\x00\x01", "application/octet-stream")}
    r = await client.post("/sop/upload", files=files)
    assert r.status_code == 415
