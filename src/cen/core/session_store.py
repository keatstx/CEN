"""SQLite-backed session persistence via aiosqlite."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aiosqlite

from cen.core.exceptions import SessionVersionConflictError
from cen.core.models import InputField, Session, SessionStatus


# New columns added across the v0.3 foundation work. Each entry is
# (column_name, column_definition) and is added via ALTER TABLE if
# missing on an existing database.
_NEW_COLUMNS: list[tuple[str, str]] = [
    ("module_version", "TEXT NOT NULL DEFAULT '1.0'"),
    ("name", "TEXT NOT NULL DEFAULT ''"),
    ("owner_id", "TEXT"),
    ("project_id", "TEXT"),
    ("version", "INTEGER NOT NULL DEFAULT 1"),
    ("pending_input_fields", "TEXT"),  # JSON list of InputField; NULL when not paused
    ("due_at", "TEXT"),  # ISO datetime; NULL = no deadline
]


def _default_session_name(module_name: str, created_at: str) -> str:
    """Auto-generated case label, e.g. 'insurance_appeal_assistant — 2026-04-07 14:32'."""
    try:
        dt = datetime.fromisoformat(created_at)
        stamp = dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        stamp = created_at
    return f"{module_name} — {stamp}"


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
                module_version TEXT NOT NULL DEFAULT '1.0',
                name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                context TEXT NOT NULL DEFAULT '{}',
                executed_nodes TEXT NOT NULL DEFAULT '[]',
                pending_node TEXT,
                pending_input_fields TEXT,
                approved_nodes TEXT NOT NULL DEFAULT '[]',
                owner_id TEXT,
                project_id TEXT,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Migrate any existing database that predates the new columns.
        await self._add_missing_columns()
        # Indexes for common filters.
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_module_name ON sessions(module_name)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_owner_id ON sessions(owner_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id)"
        )
        await self._db.commit()

    async def _add_missing_columns(self) -> None:
        assert self._db is not None
        async with self._db.execute("PRAGMA table_info(sessions)") as cursor:
            existing = {row["name"] for row in await cursor.fetchall()}
        for col_name, col_def in _NEW_COLUMNS:
            if col_name not in existing:
                await self._db.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col_name} {col_def}"
                )

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(
        self,
        module_name: str,
        context: dict | None = None,
        *,
        module_version: str = "1.0",
        name: str | None = None,
        owner_id: str | None = None,
        project_id: str | None = None,
        due_at: str | None = None,
    ) -> Session:
        now = datetime.now(timezone.utc).isoformat()
        session = Session(
            id=uuid.uuid4().hex,
            module_name=module_name,
            module_version=module_version,
            name=name or _default_session_name(module_name, now),
            status=SessionStatus.ACTIVE,
            context=context or {},
            executed_nodes=[],
            owner_id=owner_id,
            project_id=project_id,
            version=1,
            due_at=due_at,
            created_at=now,
            updated_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO sessions (id, module_name, module_version, name, status,
                                  context, executed_nodes, pending_node, approved_nodes,
                                  owner_id, project_id, version, due_at,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.module_name,
                session.module_version,
                session.name,
                session.status.value,
                json.dumps(session.context),
                json.dumps(session.executed_nodes),
                session.pending_node,
                json.dumps(session.approved_nodes),
                session.owner_id,
                session.project_id,
                session.version,
                session.due_at,
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

    async def update(
        self,
        session_id: str,
        *,
        expected_version: int | None = None,
        **fields,
    ) -> Session | None:
        existing = await self.get(session_id)
        if existing is None:
            return None

        # Optimistic concurrency check (opt-in via expected_version).
        if expected_version is not None and existing.version != expected_version:
            raise SessionVersionConflictError(
                session_id, expected_version, existing.version
            )

        allowed = {
            "context",
            "status",
            "executed_nodes",
            "pending_node",
            "pending_input_fields",
            "approved_nodes",
            "name",
            "owner_id",
            "project_id",
            "due_at",
        }
        # Note: pending_input_fields, pending_node, and due_at are also
        # allowed to be set to None (to clear). Filter out None for
        # *other* fields, but keep these three if they were explicitly
        # passed.
        nullable_fields = ("pending_node", "pending_input_fields", "due_at")
        updates: dict[str, Any] = {}
        for k, v in fields.items():
            if k not in allowed:
                continue
            if v is None and k not in nullable_fields:
                continue
            updates[k] = v
        if not updates and not any(k in fields for k in nullable_fields):
            return existing

        now = datetime.now(timezone.utc).isoformat()
        set_clauses = []
        params: list = []
        for key, value in updates.items():
            set_clauses.append(f"{key} = ?")
            if key in ("context", "executed_nodes", "approved_nodes"):
                params.append(json.dumps(value))
            elif key == "pending_input_fields":
                if value is None:
                    params.append(None)
                else:
                    # Accept either list[InputField] or list[dict]
                    serialized = [
                        f.model_dump() if hasattr(f, "model_dump") else f
                        for f in value
                    ]
                    params.append(json.dumps(serialized))
            elif key == "status":
                params.append(value.value if isinstance(value, SessionStatus) else value)
            else:
                params.append(value)
        # Always bump version + updated_at on every successful update.
        set_clauses.append("version = version + 1")
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
        self,
        module_name: str | None = None,
        owner_id: str | None = None,
        project_id: str | None = None,
        status_in: list[str] | None = None,
        limit: int = 50,
    ) -> list[Session]:
        assert self._db is not None
        clauses: list[str] = []
        params: list = []
        if module_name:
            clauses.append("module_name = ?")
            params.append(module_name)
        if owner_id:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status_in:
            placeholders = ",".join("?" for _ in status_in)
            clauses.append(f"status IN ({placeholders})")
            params.extend(status_in)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        query = f"SELECT * FROM sessions {where} ORDER BY updated_at DESC LIMIT ?"
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
        pending_input_fields: list[InputField] | None = None
        if "pending_input_fields" in row.keys() and row["pending_input_fields"]:
            try:
                raw = json.loads(row["pending_input_fields"])
                pending_input_fields = [InputField(**item) for item in raw]
            except (json.JSONDecodeError, TypeError, ValueError):
                pending_input_fields = None
        return Session(
            id=row["id"],
            module_name=row["module_name"],
            module_version=row["module_version"] if "module_version" in row.keys() else "1.0",
            name=row["name"] if "name" in row.keys() else "",
            status=SessionStatus(row["status"]),
            context=json.loads(row["context"]),
            executed_nodes=json.loads(row["executed_nodes"]),
            pending_node=row["pending_node"],
            pending_input_fields=pending_input_fields,
            approved_nodes=json.loads(row["approved_nodes"]),
            owner_id=row["owner_id"] if "owner_id" in row.keys() else None,
            project_id=row["project_id"] if "project_id" in row.keys() else None,
            version=row["version"] if "version" in row.keys() else 1,
            due_at=row["due_at"] if "due_at" in row.keys() else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
