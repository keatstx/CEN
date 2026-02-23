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


class TestHashChain:
    async def test_records_have_nonempty_hash(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        entries = await audit_store.get_by_session("s1")
        assert entries[0].record_hash != ""
        assert len(entries[0].record_hash) == 64  # SHA-256 hex length

    async def test_consecutive_hashes_differ(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "ACTION", "done", {}, "t2")
        entries = await audit_store.get_by_session("s1")
        assert entries[0].record_hash != entries[1].record_hash

    async def test_hash_chain_links_records(self, audit_store: AuditStore):
        """Each record's hash depends on the previous record's hash."""
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "ACTION", "done", {}, "t2")

        entries = await audit_store.get_by_session("s1")

        # Recompute the second hash using the first hash as prev_hash
        expected = AuditStore._compute_hash(
            entries[0].record_hash, "s1", "mod", "n2", "ACTION", "done", "{}", "t2"
        )
        assert entries[1].record_hash == expected

    async def test_first_record_uses_genesis_hash(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {"k": "v"}, "t1")
        entries = await audit_store.get_by_session("s1")

        import json
        expected = AuditStore._compute_hash(
            "0" * 64, "s1", "mod", "n1", "ACTION", "done", json.dumps({"k": "v"}), "t1"
        )
        assert entries[0].record_hash == expected

    async def test_verify_chain_valid(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "ACTION", "done", {}, "t2")

        is_valid, last_id, total = await audit_store.verify_chain()
        assert is_valid is True
        assert total == 2
        assert last_id > 0

    async def test_verify_chain_empty(self, audit_store: AuditStore):
        is_valid, last_id, total = await audit_store.verify_chain()
        assert is_valid is True
        assert last_id == 0
        assert total == 0

    async def test_verify_chain_detects_tamper(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "ACTION", "done", {}, "t2")

        # Tamper with a record's hash directly
        assert audit_store._db is not None
        await audit_store._db.execute(
            "UPDATE audit_log SET record_hash = 'tampered' WHERE id = 2"
        )
        await audit_store._db.commit()

        is_valid, last_id, total = await audit_store.verify_chain()
        assert is_valid is False
        assert last_id == 1  # Only first record verified

    async def test_verify_chain_by_session(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s2", "mod", "n2", "ACTION", "done", {}, "t2")
        await audit_store.append("s1", "mod", "n3", "ACTION", "done", {}, "t3")

        is_valid, last_id, total = await audit_store.verify_chain(session_id="s1")
        assert is_valid is True
        assert total == 2


class TestQueryFiltering:
    async def test_query_no_filters(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "CONDITION", "passed", {}, "t2")

        results = await audit_store.query()
        assert len(results) == 2

    async def test_query_by_session_id(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s2", "mod", "n2", "ACTION", "done", {}, "t2")

        results = await audit_store.query(session_id="s1")
        assert len(results) == 1
        assert results[0].session_id == "s1"

    async def test_query_by_node_type(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "CONDITION", "passed", {}, "t2")
        await audit_store.append("s1", "mod", "n3", "ACTION", "done", {}, "t3")

        results = await audit_store.query(node_type="CONDITION")
        assert len(results) == 1
        assert results[0].node_type == "CONDITION"

    async def test_query_by_outcome(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "ACTION", "failed", {}, "t2")

        results = await audit_store.query(outcome="failed")
        assert len(results) == 1
        assert results[0].outcome == "failed"

    async def test_query_by_time_range(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "2026-01-01T00:00:00Z")
        await audit_store.append("s1", "mod", "n2", "ACTION", "done", {}, "2026-01-02T00:00:00Z")
        await audit_store.append("s1", "mod", "n3", "ACTION", "done", {}, "2026-01-03T00:00:00Z")

        results = await audit_store.query(
            start_time="2026-01-01T12:00:00Z",
            end_time="2026-01-02T12:00:00Z",
        )
        assert len(results) == 1
        assert results[0].node_id == "n2"

    async def test_query_pagination(self, audit_store: AuditStore):
        for i in range(5):
            await audit_store.append("s1", "mod", f"n{i}", "ACTION", "done", {}, f"t{i}")

        page1 = await audit_store.query(limit=2, offset=0)
        page2 = await audit_store.query(limit=2, offset=2)
        page3 = await audit_store.query(limit=2, offset=4)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1
        assert page1[0].node_id == "n0"
        assert page2[0].node_id == "n2"
        assert page3[0].node_id == "n4"

    async def test_query_combined_filters(self, audit_store: AuditStore):
        await audit_store.append("s1", "mod", "n1", "ACTION", "done", {}, "t1")
        await audit_store.append("s1", "mod", "n2", "CONDITION", "done", {}, "t2")
        await audit_store.append("s2", "mod", "n3", "ACTION", "done", {}, "t3")

        results = await audit_store.query(session_id="s1", node_type="ACTION")
        assert len(results) == 1
        assert results[0].node_id == "n1"
