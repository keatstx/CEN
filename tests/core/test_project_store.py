"""Tests for ProjectStore persistence layer."""

from __future__ import annotations

import pytest

from cen.core.project_store import ProjectStore


@pytest.fixture()
async def store():
    s = ProjectStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestProjectStore:
    async def test_create_and_get(self, store: ProjectStore):
        project = await store.create(
            name="Mrs. Jones",
            description="Medical debt + insurance appeal",
            owner_id="user-alice",
        )
        assert project.name == "Mrs. Jones"
        assert project.description == "Medical debt + insurance appeal"
        assert project.owner_id == "user-alice"
        assert project.id

        fetched = await store.get(project.id)
        assert fetched is not None
        assert fetched.id == project.id
        assert fetched.name == "Mrs. Jones"

    async def test_create_without_owner(self, store: ProjectStore):
        project = await store.create("Unowned project")
        assert project.owner_id is None
        assert project.description == ""

    async def test_get_nonexistent(self, store: ProjectStore):
        assert await store.get("does_not_exist") is None

    async def test_update_name_and_description(self, store: ProjectStore):
        project = await store.create("Original")
        updated = await store.update(
            project.id, name="Renamed", description="With detail"
        )
        assert updated is not None
        assert updated.name == "Renamed"
        assert updated.description == "With detail"
        assert updated.updated_at >= project.updated_at

    async def test_update_partial(self, store: ProjectStore):
        project = await store.create("Original", description="Keep me")
        updated = await store.update(project.id, name="Renamed only")
        assert updated is not None
        assert updated.name == "Renamed only"
        assert updated.description == "Keep me"

    async def test_update_nonexistent(self, store: ProjectStore):
        assert await store.update("nope", name="x") is None

    async def test_list_filtered_by_owner(self, store: ProjectStore):
        await store.create("Alice 1", owner_id="alice")
        await store.create("Bob 1", owner_id="bob")
        await store.create("Alice 2", owner_id="alice")
        results = await store.list_projects(owner_id="alice")
        assert len(results) == 2
        assert all(p.owner_id == "alice" for p in results)

    async def test_list_all(self, store: ProjectStore):
        await store.create("a", owner_id="alice")
        await store.create("b", owner_id="bob")
        await store.create("c")  # unowned
        assert len(await store.list_projects()) == 3

    async def test_delete(self, store: ProjectStore):
        project = await store.create("Disposable")
        assert await store.delete(project.id) is True
        assert await store.get(project.id) is None

    async def test_delete_nonexistent(self, store: ProjectStore):
        assert await store.delete("nope") is False

    async def test_get_or_create_default_creates_when_missing(
        self, store: ProjectStore
    ):
        default = await store.get_or_create_default(owner_id="alice")
        assert default.name == "Default"
        assert default.owner_id == "alice"

    async def test_get_or_create_default_returns_existing(
        self, store: ProjectStore
    ):
        first = await store.get_or_create_default(owner_id="alice")
        second = await store.get_or_create_default(owner_id="alice")
        assert first.id == second.id

    async def test_get_or_create_default_per_owner(self, store: ProjectStore):
        alice_default = await store.get_or_create_default(owner_id="alice")
        bob_default = await store.get_or_create_default(owner_id="bob")
        assert alice_default.id != bob_default.id
        assert alice_default.owner_id == "alice"
        assert bob_default.owner_id == "bob"

    async def test_get_or_create_default_unowned(self, store: ProjectStore):
        first = await store.get_or_create_default(owner_id=None)
        second = await store.get_or_create_default(owner_id=None)
        assert first.id == second.id
        assert first.owner_id is None
