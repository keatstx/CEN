"""SQLite-backed store for concierge chat history.

Append-only by design: chat is part of the audit trail. The schema
mirrors `audit_events` in spirit — no update/delete code paths besides
the redaction helper.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aiosqlite

from cen.core.models import ChatMessage, ConciergeCitation


class ChatMessageStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations_json TEXT NOT NULL DEFAULT '[]',
                mode TEXT NOT NULL DEFAULT '',
                owner_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_case_id ON chat_messages(case_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_owner_id ON chat_messages(owner_id)"
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def append(
        self,
        *,
        case_id: str,
        role: str,
        content: str,
        citations: Optional[List[ConciergeCitation]] = None,
        mode: str = "",
        owner_id: Optional[str] = None,
    ) -> ChatMessage:
        now = datetime.now(timezone.utc).isoformat()
        msg = ChatMessage(
            id=uuid.uuid4().hex,
            case_id=case_id,
            role=role,
            content=content,
            citations=citations or [],
            mode=mode,
            owner_id=owner_id,
            created_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO chat_messages
                (id, case_id, role, content, citations_json, mode, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.case_id,
                msg.role,
                msg.content,
                json.dumps([c.model_dump() for c in msg.citations]),
                msg.mode,
                msg.owner_id,
                msg.created_at,
            ),
        )
        await self._db.commit()
        return msg

    async def list_for_case(
        self,
        case_id: str,
        *,
        owner_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[ChatMessage]:
        """Return chronological history for a case (oldest first)."""
        assert self._db is not None
        clauses = ["case_id = ?"]
        params: list = [case_id]
        if owner_id is not None:
            clauses.append("(owner_id IS NULL OR owner_id = ?)")
            params.append(owner_id)
        where = " AND ".join(clauses)
        query = f"SELECT * FROM chat_messages WHERE {where} ORDER BY created_at ASC"
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_message(row) for row in rows]

    async def list_recent_for_case(
        self,
        case_id: str,
        *,
        owner_id: Optional[str] = None,
        limit: int = 6,
    ) -> List[ChatMessage]:
        """Return the most recent N messages, oldest-first.

        Used by the prompt assembler to give the synthesis layer
        short-term conversational context without blowing up tokens.
        """
        assert self._db is not None
        clauses = ["case_id = ?"]
        params: list = [case_id]
        if owner_id is not None:
            clauses.append("(owner_id IS NULL OR owner_id = ?)")
            params.append(owner_id)
        where = " AND ".join(clauses)
        # Pull DESC then reverse so we get the *latest* N, oldest-first.
        async with self._db.execute(
            f"SELECT * FROM chat_messages WHERE {where} "
            f"ORDER BY created_at DESC LIMIT {int(limit)}",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
        out = [self._row_to_message(row) for row in rows]
        out.reverse()
        return out

    @staticmethod
    def _row_to_message(row: aiosqlite.Row) -> ChatMessage:
        try:
            citations = [
                ConciergeCitation(**raw)
                for raw in json.loads(row["citations_json"] or "[]")
            ]
        except Exception:  # noqa: BLE001
            citations = []
        return ChatMessage(
            id=row["id"],
            case_id=row["case_id"],
            role=row["role"],
            content=row["content"],
            citations=citations,
            mode=row["mode"] or "",
            owner_id=row["owner_id"],
            created_at=row["created_at"],
        )
