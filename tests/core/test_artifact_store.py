"""Unit tests for ArtifactStore persistence."""

from __future__ import annotations

import pytest

from cen.core.artifact_store import ArtifactStore


@pytest.fixture()
async def store():
    s = ArtifactStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestArtifactStore:
    async def test_create_and_get(self, store: ArtifactStore):
        artifact = await store.create(
            case_id="case-1",
            filename="bill.pdf",
            content_type="application/pdf",
            size=12345,
            storage_key="proj-1/case-1/abc",
            project_id="proj-1",
            node_id="upload_step",
            owner_id="alice",
        )
        assert artifact.id
        assert artifact.filename == "bill.pdf"
        assert artifact.size == 12345

        fetched = await store.get(artifact.id)
        assert fetched is not None
        assert fetched.case_id == "case-1"
        assert fetched.owner_id == "alice"
        assert fetched.node_id == "upload_step"

    async def test_get_nonexistent(self, store: ArtifactStore):
        assert await store.get("nope") is None

    async def test_list_for_case(self, store: ArtifactStore):
        for i in range(3):
            await store.create(
                case_id="case-1",
                filename=f"file_{i}.pdf",
                content_type="application/pdf",
                size=100,
                storage_key=f"k_{i}",
                owner_id="alice",
            )
        await store.create(
            case_id="case-2",
            filename="other.pdf",
            content_type="application/pdf",
            size=100,
            storage_key="k_other",
            owner_id="alice",
        )
        results = await store.list_for_case("case-1")
        assert len(results) == 3
        assert all(a.case_id == "case-1" for a in results)

    async def test_list_filters_by_owner(self, store: ArtifactStore):
        await store.create(
            case_id="case-1",
            filename="alice.pdf",
            content_type="application/pdf",
            size=100,
            storage_key="k_alice",
            owner_id="alice",
        )
        await store.create(
            case_id="case-1",
            filename="bob.pdf",
            content_type="application/pdf",
            size=100,
            storage_key="k_bob",
            owner_id="bob",
        )
        alice_only = await store.list_for_case("case-1", owner_id="alice")
        assert len(alice_only) == 1
        assert alice_only[0].owner_id == "alice"

    async def test_delete(self, store: ArtifactStore):
        artifact = await store.create(
            case_id="case-1",
            filename="bill.pdf",
            content_type="application/pdf",
            size=100,
            storage_key="k1",
        )
        assert await store.delete(artifact.id) is True
        assert await store.get(artifact.id) is None

    async def test_delete_nonexistent(self, store: ArtifactStore):
        assert await store.delete("nope") is False
