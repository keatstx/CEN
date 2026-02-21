"""Tests for SessionStore persistence layer."""

from __future__ import annotations

import pytest

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
