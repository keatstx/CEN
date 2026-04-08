"""Tests for the /cases/{id}/summary and /cases/{id}/export endpoints."""

from __future__ import annotations

import io
import json
import zipfile

from httpx import AsyncClient


_FAKE_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"


async def _create_walked_case(client: AsyncClient) -> str:
    """Create a charity_care case, walk it forward a few steps so
    there's real captured info to render."""
    cr = await client.post(
        "/cases", json={"module_name": "charity_care_navigator"}
    )
    cid = cr.json()["id"]
    # Kick off with patient identity pre-filled to skip the intake
    # pause and land on the HIPAA approval gate.
    await client.post(
        f"/execute?session_id={cid}",
        json={
            "module_name": "charity_care_navigator",
            "context": {
                "patient_name": "Jane Doe",
                "patient_dob": "1980-01-01",
                "patient_phone": "555-1234",
            },
        },
    )
    # Approve HIPAA so consent_granted gets auto_set.
    await client.post(f"/cases/{cid}/approve")
    # Upload a fake document.
    await client.post(
        f"/cases/{cid}/artifacts",
        files={"file": ("bill.pdf", _FAKE_PDF, "application/pdf")},
    )
    return cid


class TestCaseSummary:
    async def test_summary_html_returns_200_and_html(
        self, client: AsyncClient
    ):
        cid = await _create_walked_case(client)
        resp = await client.get(f"/cases/{cid}/summary")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        body = resp.text
        # Patient identity should appear in the rendered summary.
        assert "Jane Doe" in body
        assert "1980-01-01" in body
        # The captured-info section header should be present.
        assert "Information collected" in body
        # The document should be listed.
        assert "bill.pdf" in body
        # Self-contained — no external CSS link.
        assert "<style>" in body
        assert "<link" not in body

    async def test_summary_json_format(self, client: AsyncClient):
        cid = await _create_walked_case(client)
        resp = await client.get(f"/cases/{cid}/summary?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["case"]["id"] == cid
        assert data["case"]["module_name"] == "charity_care_navigator"
        keys = {item["key"] for item in data["captured_information"]}
        assert "patient_name" in keys
        assert "consent_granted" in keys
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "bill.pdf"

    async def test_summary_nonexistent_case_404(self, client: AsyncClient):
        resp = await client.get("/cases/does_not_exist/summary")
        assert resp.status_code == 404

    async def test_summary_includes_executed_steps(
        self, client: AsyncClient
    ):
        cid = await _create_walked_case(client)
        resp = await client.get(f"/cases/{cid}/summary?format=json")
        data = resp.json()
        # At minimum: intake_start ran (then identity_verification was
        # skipped because patient identity was pre-filled).
        assert len(data["case"]["executed_nodes"]) >= 2


class TestCaseExport:
    async def test_export_returns_zip_with_summary_and_documents(
        self, client: AsyncClient
    ):
        cid = await _create_walked_case(client)
        resp = await client.get(f"/cases/{cid}/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert "case_" in resp.headers["content-disposition"]

        # Open the ZIP and check its contents.
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = set(zf.namelist())
        assert "summary.html" in names
        assert "summary.json" in names
        assert "documents/bill.pdf" in names

        # Summary HTML matches what /summary returns.
        html_content = zf.read("summary.html").decode("utf-8")
        assert "Jane Doe" in html_content

        # JSON parses cleanly.
        json_content = json.loads(zf.read("summary.json").decode("utf-8"))
        assert json_content["case"]["id"] == cid

        # Document bytes are intact.
        assert zf.read("documents/bill.pdf") == _FAKE_PDF

    async def test_export_with_no_artifacts_still_works(
        self, client: AsyncClient
    ):
        cr = await client.post(
            "/cases", json={"module_name": "charity_care_navigator"}
        )
        cid = cr.json()["id"]
        resp = await client.get(f"/cases/{cid}/export")
        assert resp.status_code == 200
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = set(zf.namelist())
        assert "summary.html" in names
        assert "summary.json" in names
        # No documents/ entries when no files are attached.
        assert not any(n.startswith("documents/") for n in names)

    async def test_export_nonexistent_case_404(self, client: AsyncClient):
        resp = await client.get("/cases/does_not_exist/export")
        assert resp.status_code == 404

    async def test_export_handles_filename_collisions(
        self, client: AsyncClient
    ):
        cid = await _create_walked_case(client)
        # Upload another file with the same name.
        await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("bill.pdf", _FAKE_PDF + b"\n%EOF", "application/pdf")},
        )
        resp = await client.get(f"/cases/{cid}/export")
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        doc_names = [n for n in zf.namelist() if n.startswith("documents/")]
        # Both files present under unique names.
        assert len(doc_names) == 2
        assert "documents/bill.pdf" in doc_names
        assert any("bill_1" in n for n in doc_names)
