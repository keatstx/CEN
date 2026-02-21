"""SQLite-backed session persistence via aiosqlite."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aiosqlite

from cen.core.models import Session, SessionStatus


class SessionStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                module_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                context TEXT NOT NULL DEFAULT '{}',
                executed_nodes TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(self, module_name: str, context: dict | None = None) -> Session:
        now = datetime.now(timezone.utc).isoformat()
        session = Session(
            id=uuid.uuid4().hex,
            module_name=module_name,
            status=SessionStatus.ACTIVE,
            context=context or {},
            executed_nodes=[],
            created_at=now,
            updated_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO sessions (id, module_name, status, context, executed_nodes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.module_name,
                session.status.value,
                json.dumps(session.context),
                json.dumps(session.executed_nodes),
                session.created_at,
                session.updated_at,
            ),
        )
        await self._db.commit()
        return session

    async def get(self, session_id: str) -> Session | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    async def update(self, session_id: str, **fields) -> Session | None:
        existing = await self.get(session_id)
        if existing is None:
            return None

        allowed = {"context", "status", "executed_nodes"}
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        set_clauses = []
        params: list = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = ?")
            if key in ("context", "executed_nodes"):
                params.append(json.dumps(value))
            elif key == "status":
                params.append(value.value if isinstance(value, SessionStatus) else value)
            else:
                params.append(value)
        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(session_id)

        assert self._db is not None
        await self._db.execute(
            f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )
        await self._db.commit()
        return await self.get(session_id)

    async def list_sessions(
        self, module_name: str | None = None, limit: int = 50
    ) -> list[Session]:
        assert self._db is not None
        if module_name:
            query = "SELECT * FROM sessions WHERE module_name = ? ORDER BY created_at DESC LIMIT ?"
            params = (module_name, limit)
        else:
            query = "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?"
            params = (limit,)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_session(row) for row in rows]

    async def delete(self, session_id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM sessions WHERE id = ?", (session_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_session(row: aiosqlite.Row) -> Session:
        return Session(
            id=row["id"],
            module_name=row["module_name"],
            status=SessionStatus(row["status"]),
            context=json.loads(row["context"]),
            executed_nodes=json.loads(row["executed_nodes"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
