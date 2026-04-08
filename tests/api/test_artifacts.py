"""End-to-end tests for the case artifact upload + download endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# Real PDF magic bytes — `%PDF-` followed by version + minimal valid content.
_FAKE_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"
_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
_FAKE_NOT_PDF = b"<html>not a pdf</html>"


async def _create_case(client: AsyncClient) -> str:
    resp = await client.post(
        "/cases", json={"module_name": "charity_care_navigator"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestArtifactUpload:
    async def test_upload_pdf_succeeds(self, client: AsyncClient):
        cid = await _create_case(client)
        resp = await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("bill.pdf", _FAKE_PDF, "application/pdf")},
            data={"node_id": "upload_step"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "bill.pdf"
        assert data["content_type"] == "application/pdf"
        assert data["size"] == len(_FAKE_PDF)
        assert data["case_id"] == cid
        assert data["node_id"] == "upload_step"
        assert data["owner_id"] == "default-operator"
        assert data["storage_key"]

    async def test_upload_png_succeeds(self, client: AsyncClient):
        cid = await _create_case(client)
        resp = await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("photo.png", _FAKE_PNG, "image/png")},
        )
        assert resp.status_code == 201
        assert resp.json()["content_type"] == "image/png"

    async def test_upload_to_nonexistent_case_404(self, client: AsyncClient):
        resp = await client.post(
            "/cases/does-not-exist/artifacts",
            files={"file": ("x.pdf", _FAKE_PDF, "application/pdf")},
        )
        assert resp.status_code == 404

    async def test_upload_unsupported_content_type_415(
        self, client: AsyncClient
    ):
        cid = await _create_case(client)
        resp = await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("bin.exe", b"MZ\x90\x00", "application/x-msdownload")},
        )
        assert resp.status_code == 415

    async def test_upload_mismatched_magic_bytes_415(self, client: AsyncClient):
        cid = await _create_case(client)
        resp = await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("evil.pdf", _FAKE_NOT_PDF, "application/pdf")},
        )
        assert resp.status_code == 415

    async def test_upload_filename_sanitized(self, client: AsyncClient):
        cid = await _create_case(client)
        resp = await client.post(
            f"/cases/{cid}/artifacts",
            files={
                "file": ("../../../etc/passwd.pdf", _FAKE_PDF, "application/pdf"),
            },
        )
        assert resp.status_code == 201
        # Path separators stripped, no leading dots.
        assert "/" not in resp.json()["filename"]
        assert "\\" not in resp.json()["filename"]


class TestArtifactList:
    async def test_list_empty(self, client: AsyncClient):
        cid = await _create_case(client)
        resp = await client.get(f"/cases/{cid}/artifacts")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_after_upload(self, client: AsyncClient):
        cid = await _create_case(client)
        for i in range(3):
            await client.post(
                f"/cases/{cid}/artifacts",
                files={
                    "file": (f"f_{i}.pdf", _FAKE_PDF, "application/pdf"),
                },
            )
        resp = await client.get(f"/cases/{cid}/artifacts")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    async def test_list_nonexistent_case_404(self, client: AsyncClient):
        resp = await client.get("/cases/nope/artifacts")
        assert resp.status_code == 404


class TestArtifactDownload:
    async def test_download_returns_bytes(self, client: AsyncClient):
        cid = await _create_case(client)
        upload = await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("bill.pdf", _FAKE_PDF, "application/pdf")},
        )
        aid = upload.json()["id"]

        resp = await client.get(f"/artifacts/{aid}")
        assert resp.status_code == 200
        assert resp.content == _FAKE_PDF
        assert resp.headers["content-type"].startswith("application/pdf")
        assert "bill.pdf" in resp.headers["content-disposition"]
        assert resp.headers["cache-control"] == "private, no-store"

    async def test_download_nonexistent_404(self, client: AsyncClient):
        resp = await client.get("/artifacts/does-not-exist")
        assert resp.status_code == 404


class TestArtifactDelete:
    async def test_delete_artifact_succeeds(self, client: AsyncClient):
        cid = await _create_case(client)
        upload = await client.post(
            f"/cases/{cid}/artifacts",
            files={"file": ("bill.pdf", _FAKE_PDF, "application/pdf")},
        )
        aid = upload.json()["id"]

        # Confirm it's listed.
        list_resp = await client.get(f"/cases/{cid}/artifacts")
        assert any(a["id"] == aid for a in list_resp.json())

        # Delete.
        del_resp = await client.delete(f"/artifacts/{aid}")
        assert del_resp.status_code == 204

        # No longer listed.
        list_after = await client.get(f"/cases/{cid}/artifacts")
        assert all(a["id"] != aid for a in list_after.json())

        # Download now 404s.
        get_after = await client.get(f"/artifacts/{aid}")
        assert get_after.status_code == 404

    async def test_delete_nonexistent_artifact_404(self, client: AsyncClient):
        resp = await client.delete("/artifacts/does-not-exist")
        assert resp.status_code == 404

    async def test_delete_supports_multi_upload_then_delete_one(
        self, client: AsyncClient
    ):
        cid = await _create_case(client)
        ids = []
        for i in range(3):
            r = await client.post(
                f"/cases/{cid}/artifacts",
                files={"file": (f"f_{i}.pdf", _FAKE_PDF, "application/pdf")},
            )
            ids.append(r.json()["id"])
        # Delete the middle one.
        await client.delete(f"/artifacts/{ids[1]}")
        # The other two are still there.
        list_resp = await client.get(f"/cases/{cid}/artifacts")
        remaining = {a["id"] for a in list_resp.json()}
        assert ids[0] in remaining
        assert ids[1] not in remaining
        assert ids[2] in remaining
