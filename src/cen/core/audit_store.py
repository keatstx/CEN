"""Append-only SQLite-backed audit log for compliance-grade tracking."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import aiosqlite

from cen.core.models import AuditEntry


class AuditStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                module TEXT NOT NULL,
                node_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                outcome TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '{}',
                timestamp TEXT NOT NULL,
                record_hash TEXT NOT NULL DEFAULT ''
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_log (session_id)"
        )
        await self._db.commit()

        # Schema migration: add record_hash column if missing
        await self._migrate_add_record_hash()

    async def _migrate_add_record_hash(self) -> None:
        assert self._db is not None
        async with self._db.execute("PRAGMA table_info(audit_log)") as cursor:
            columns = [row[1] async for row in cursor]
        if "record_hash" not in columns:
            await self._db.execute(
                "ALTER TABLE audit_log ADD COLUMN record_hash TEXT NOT NULL DEFAULT ''"
            )
            await self._backfill_hashes()
            await self._db.commit()

    async def _backfill_hashes(self) -> None:
        """Backfill hash chain for existing rows missing hashes."""
        assert self._db is not None
        async with self._db.execute(
            "SELECT id, session_id, module, node_id, node_type, outcome, context, timestamp "
            "FROM audit_log ORDER BY id ASC"
        ) as cursor:
            prev_hash = "0" * 64
            async for row in cursor:
                record_hash = self._compute_hash(
                    prev_hash, row[1], row[2], row[3], row[4], row[5], row[6], row[7]
                )
                await self._db.execute(
                    "UPDATE audit_log SET record_hash = ? WHERE id = ?",
                    (record_hash, row[0]),
                )
                prev_hash = record_hash

    @staticmethod
    def _compute_hash(
        prev_hash: str,
        session_id: str,
        module: str,
        node_id: str,
        node_type: str,
        outcome: str,
        context_json: str,
        timestamp: str,
    ) -> str:
        payload = "|".join([
            prev_hash, session_id, module, node_id, node_type, outcome, context_json, timestamp
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def append(
        self,
        session_id: str,
        module: str,
        node_id: str,
        node_type: str,
        outcome: str,
        context: dict[str, Any],
        timestamp: str,
    ) -> None:
        assert self._db is not None
        context_json = json.dumps(context)

        # Fetch previous record's hash (global chain, not per-session)
        async with self._db.execute(
            "SELECT record_hash FROM audit_log ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            prev_hash = row[0] if row and row[0] else "0" * 64

        record_hash = self._compute_hash(
            prev_hash, session_id, module, node_id, node_type, outcome, context_json, timestamp
        )

        await self._db.execute(
            """
            INSERT INTO audit_log (session_id, module, node_id, node_type, outcome, context, timestamp, record_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, module, node_id, node_type, outcome, context_json, timestamp, record_hash),
        )
        await self._db.commit()

    async def get_by_session(self, session_id: str) -> list[AuditEntry]:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM audit_log WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    async def query(
        self,
        session_id: Optional[str] = None,
        node_type: Optional[str] = None,
        outcome: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[AuditEntry]:
        assert self._db is not None
        conditions: list[str] = []
        params: list[Any] = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if node_type is not None:
            conditions.append("node_type = ?")
            params.append(node_type)
        if outcome is not None:
            conditions.append("outcome = ?")
            params.append(outcome)
        if start_time is not None:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("timestamp <= ?")
            params.append(end_time)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM audit_log{where} ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_entry(row) for row in rows]

    async def verify_chain(
        self, session_id: Optional[str] = None
    ) -> tuple[bool, int, int]:
        """Walk records in id ASC order, recompute each hash, return (is_valid, last_verified_id, total_records).

        Note: The hash chain is global (not per-session). When session_id is provided,
        we verify the full chain up to the last record for that session, but only count
        records belonging to that session.
        """
        assert self._db is not None

        # Always walk the full chain to verify integrity
        async with self._db.execute(
            "SELECT id, session_id, module, node_id, node_type, outcome, context, timestamp, record_hash "
            "FROM audit_log ORDER BY id ASC"
        ) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            return (True, 0, 0)

        prev_hash = "0" * 64
        last_verified_id = 0
        session_count = 0

        for row in rows:
            row_id = row[0]
            row_session = row[1]
            expected = self._compute_hash(
                prev_hash, row[1], row[2], row[3], row[4], row[5], row[6], row[7]
            )
            if row[8] != expected:
                if session_id is not None:
                    return (False, last_verified_id, session_count)
                return (False, last_verified_id, len(rows))
            prev_hash = row[8]

            if session_id is None or row_session == session_id:
                last_verified_id = row_id
                if session_id is not None:
                    session_count += 1

        total = session_count if session_id is not None else len(rows)
        return (True, last_verified_id, total)

    @staticmethod
    def _row_to_entry(row: aiosqlite.Row) -> AuditEntry:
        return AuditEntry(
            id=row["id"],
            session_id=row["session_id"],
            module=row["module"],
            node_id=row["node_id"],
            node_type=row["node_type"],
            outcome=row["outcome"],
            context=json.loads(row["context"]),
            timestamp=row["timestamp"],
            record_hash=row["record_hash"],
        )
