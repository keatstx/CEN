"""Tests for SessionStore persistence layer."""

from __future__ import annotations

import pytest

from cen.core.exceptions import SessionVersionConflictError
from cen.core.models import SessionStatus
from cen.core.session_store import SessionStore


@pytest.fixture()
async def store():
    s = SessionStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestSessionStore:
    async def test_create_and_get(self, store: SessionStore):
        session = await store.create("test_module", {"key": "value"})
        assert session.module_name == "test_module"
        assert session.context == {"key": "value"}
        assert session.status == SessionStatus.ACTIVE
        assert session.executed_nodes == []

        fetched = await store.get(session.id)
        assert fetched is not None
        assert fetched.id == session.id
        assert fetched.context == {"key": "value"}

    async def test_get_nonexistent(self, store: SessionStore):
        result = await store.get("does_not_exist")
        assert result is None

    async def test_update_context(self, store: SessionStore):
        session = await store.create("mod", {"a": 1})
        updated = await store.update(session.id, context={"a": 1, "b": 2})
        assert updated is not None
        assert updated.context == {"a": 1, "b": 2}
        assert updated.updated_at >= session.updated_at

    async def test_update_status(self, store: SessionStore):
        session = await store.create("mod")
        updated = await store.update(session.id, status=SessionStatus.COMPLETED)
        assert updated is not None
        assert updated.status == SessionStatus.COMPLETED

    async def test_update_nonexistent(self, store: SessionStore):
        result = await store.update("nope", context={"x": 1})
        assert result is None

    async def test_list_all(self, store: SessionStore):
        await store.create("mod_a")
        await store.create("mod_b")
        await store.create("mod_a")
        sessions = await store.list_sessions()
        assert len(sessions) == 3

    async def test_list_filtered(self, store: SessionStore):
        await store.create("mod_a")
        await store.create("mod_b")
        await store.create("mod_a")
        sessions = await store.list_sessions(module_name="mod_a")
        assert len(sessions) == 2
        assert all(s.module_name == "mod_a" for s in sessions)

    async def test_delete(self, store: SessionStore):
        session = await store.create("mod")
        assert await store.delete(session.id) is True
        assert await store.get(session.id) is None

    async def test_delete_nonexistent(self, store: SessionStore):
        assert await store.delete("nope") is False

    async def test_create_auto_generates_name(self, store: SessionStore):
        session = await store.create("insurance_appeal_assistant")
        assert session.name.startswith("insurance_appeal_assistant — ")
        assert len(session.name) > len("insurance_appeal_assistant — ")

    async def test_create_with_explicit_name(self, store: SessionStore):
        session = await store.create("mod", name="Mrs. Jones — UHC denial")
        assert session.name == "Mrs. Jones — UHC denial"

    async def test_create_with_module_version_and_owner_and_project(
        self, store: SessionStore
    ):
        session = await store.create(
            "mod",
            module_version="2.1",
            owner_id="user-abc",
            project_id="proj-123",
        )
        assert session.module_version == "2.1"
        assert session.owner_id == "user-abc"
        assert session.project_id == "proj-123"
        # Round-trip via get to ensure persistence.
        fetched = await store.get(session.id)
        assert fetched is not None
        assert fetched.module_version == "2.1"
        assert fetched.owner_id == "user-abc"
        assert fetched.project_id == "proj-123"

    async def test_version_starts_at_one_and_bumps_on_update(
        self, store: SessionStore
    ):
        session = await store.create("mod")
        assert session.version == 1
        updated = await store.update(session.id, context={"a": 1})
        assert updated is not None
        assert updated.version == 2
        updated2 = await store.update(updated.id, status=SessionStatus.COMPLETED)
        assert updated2 is not None
        assert updated2.version == 3

    async def test_optimistic_concurrency_success(self, store: SessionStore):
        session = await store.create("mod")
        updated = await store.update(
            session.id, expected_version=1, context={"a": 1}
        )
        assert updated is not None
        assert updated.version == 2

    async def test_optimistic_concurrency_conflict(self, store: SessionStore):
        session = await store.create("mod")
        # First update bumps version to 2.
        await store.update(session.id, context={"a": 1})
        # Second update with stale expected_version should raise.
        with pytest.raises(SessionVersionConflictError):
            await store.update(session.id, expected_version=1, context={"a": 2})

    async def test_update_name(self, store: SessionStore):
        session = await store.create("mod")
        updated = await store.update(session.id, name="Renamed case")
        assert updated is not None
        assert updated.name == "Renamed case"

    async def test_list_filtered_by_owner(self, store: SessionStore):
        await store.create("mod", owner_id="alice")
        await store.create("mod", owner_id="bob")
        await store.create("mod", owner_id="alice")
        sessions = await store.list_sessions(owner_id="alice")
        assert len(sessions) == 2
        assert all(s.owner_id == "alice" for s in sessions)

    async def test_list_filtered_by_project(self, store: SessionStore):
        await store.create("mod", project_id="proj-1")
        await store.create("mod", project_id="proj-2")
        sessions = await store.list_sessions(project_id="proj-1")
        assert len(sessions) == 1
        assert sessions[0].project_id == "proj-1"
