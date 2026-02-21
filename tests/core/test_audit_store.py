"""Tests for AuditStore append-only persistence layer."""

from __future__ import annotations

import pytest

from cen.core.audit_store import AuditStore


@pytest.fixture()
async def audit_store():
    s = AuditStore(":memory:")
    await s.initialize()
    yield s
    await s.close()


class TestAuditStore:
    async def test_append_and_get(self, audit_store: AuditStore):
        await audit_store.append(
            session_id="sess1",
            module="test_mod",
            node_id="node_a",
            node_type="ACTION",
            outcome="done",
            context={"key": "value"},
            timestamp="2026-01-01T00:00:00+00:00",
        )
        entries = await audit_store.get_by_session("sess1")
        assert len(entries) == 1
        assert entries[0].session_id == "sess1"
        assert entries[0].module == "test_mod"
        assert entries[0].node_id == "node_a"
        assert entries[0].node_type == "ACTION"
        assert entries[0].outcome == "done"
        assert entries[0].context == {"key": "value"}
        assert entries[0].timestamp == "2026-01-01T00:00:00+00:00"
        assert entries[0].id == 1

    async def test_multiple_entries_ordered(self, audit_store: AuditStore):
        for i in range(3):
            await audit_store.append(
                session_id="sess1",
                module="mod",
                node_id=f"node_{i}",
                node_type="ACTION",
                outcome="done",
                context={},
                timestamp=f"2026-01-01T00:00:0{i}+00:00",
            )
        entries = await audit_store.get_by_session("sess1")
        assert len(entries) == 3
        assert [e.node_id for e in entries] == ["node_0", "node_1", "node_2"]
        assert entries[0].id < entries[1].id < entries[2].id

    async def test_get_unknown_session_returns_empty(self, audit_store: AuditStore):
        entries = await audit_store.get_by_session("nonexistent")
        assert entries == []

    async def test_no_update_or_delete_methods(self, audit_store: AuditStore):
        assert not hasattr(audit_store, "update")
        assert not hasattr(audit_store, "delete")

    async def test_entries_scoped_to_session(self, audit_store: AuditStore):
        await audit_store.append("sess1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("sess2", "mod", "n2", "ACTION", "done", {}, "t2")
        await audit_store.append("sess1", "mod", "n3", "ACTION", "done", {}, "t3")

        entries1 = await audit_store.get_by_session("sess1")
        entries2 = await audit_store.get_by_session("sess2")
        assert len(entries1) == 2
        assert len(entries2) == 1
        assert entries2[0].node_id == "n2"
