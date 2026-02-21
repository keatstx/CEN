"""Append-only SQLite-backed audit log for compliance-grade tracking."""

from __future__ import annotations

import json
from typing import Any

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
                timestamp TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_session_id ON audit_log (session_id)"
        )
        await self._db.commit()

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
        await self._db.execute(
            """
            INSERT INTO audit_log (session_id, module, node_id, node_type, outcome, context, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, module, node_id, node_type, outcome, json.dumps(context), timestamp),
        )
        await self._db.commit()

    async def get_by_session(self, session_id: str) -> list[AuditEntry]:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM audit_log WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            AuditEntry(
                id=row["id"],
                session_id=row["session_id"],
                module=row["module"],
                node_id=row["node_id"],
                node_type=row["node_type"],
                outcome=row["outcome"],
                context=json.loads(row["context"]),
                timestamp=row["timestamp"],
            )
            for row in rows
        ]
