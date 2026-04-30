"""SQLite-backed metadata store for uploaded SOPs.

The bytes live in the StorageBackend keyed by `storage_key`. Parse and
extraction outputs (canonical markdown, draft AOPDefinition,
validation issues) are cached here so re-running them is idempotent.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import aiosqlite

from cen.core.models import AOPDefinition, SOPRecord, ValidationIssue


class SOPStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS sops (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                storage_key TEXT NOT NULL,
                status TEXT NOT NULL,
                canonical_md TEXT,
                draft_module_json TEXT,
                validation_issues_json TEXT,
                promoted_module_name TEXT,
                promoted_module_version TEXT,
                owner_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sops_owner_id ON sops(owner_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_sops_status ON sops(status)"
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(
        self,
        *,
        filename: str,
        content_type: str,
        size: int,
        storage_key: str,
        owner_id: Optional[str] = None,
    ) -> SOPRecord:
        now = datetime.now(timezone.utc).isoformat()
        record = SOPRecord(
            id=uuid.uuid4().hex,
            filename=filename,
            content_type=content_type,
            size=size,
            storage_key=storage_key,
            status="uploaded",
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO sops (
                id, filename, content_type, size, storage_key, status,
                canonical_md, draft_module_json, validation_issues_json,
                promoted_module_name, promoted_module_version,
                owner_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?)
            """,
            (
                record.id,
                record.filename,
                record.content_type,
                record.size,
                record.storage_key,
                record.status,
                record.owner_id,
                record.created_at,
                record.updated_at,
            ),
        )
        await self._db.commit()
        return record

    async def get(self, sop_id: str) -> SOPRecord | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM sops WHERE id = ?", (sop_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    async def list(self, owner_id: Optional[str] = None) -> List[SOPRecord]:
        assert self._db is not None
        if owner_id is None:
            query = "SELECT * FROM sops ORDER BY created_at DESC"
            params: tuple = ()
        else:
            query = "SELECT * FROM sops WHERE owner_id = ? ORDER BY created_at DESC"
            params = (owner_id,)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def update_parsed(
        self, sop_id: str, *, canonical_md: str
    ) -> SOPRecord | None:
        return await self._update(
            sop_id,
            status="parsed",
            canonical_md=canonical_md,
            draft_module_json=None,
            validation_issues_json=None,
        )

    async def update_extracted(
        self,
        sop_id: str,
        *,
        draft_module: AOPDefinition,
        validation_issues: List[ValidationIssue],
    ) -> SOPRecord | None:
        return await self._update(
            sop_id,
            status="extracted",
            draft_module_json=draft_module.model_dump_json(),
            validation_issues_json=json.dumps(
                [i.model_dump() for i in validation_issues]
            ),
        )

    async def update_promoted(
        self,
        sop_id: str,
        *,
        module_name: str,
        module_version: str,
    ) -> SOPRecord | None:
        return await self._update(
            sop_id,
            status="promoted",
            promoted_module_name=module_name,
            promoted_module_version=module_version,
        )

    async def update_failed(self, sop_id: str) -> SOPRecord | None:
        return await self._update(sop_id, status="failed")

    async def delete(self, sop_id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute("DELETE FROM sops WHERE id = ?", (sop_id,))
        await self._db.commit()
        return cursor.rowcount > 0

    async def _update(self, sop_id: str, **fields) -> SOPRecord | None:
        if not fields:
            return await self.get(sop_id)
        assert self._db is not None
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields.keys())
        params = list(fields.values()) + [sop_id]
        await self._db.execute(f"UPDATE sops SET {sets} WHERE id = ?", params)
        await self._db.commit()
        return await self.get(sop_id)

    @staticmethod
    def _row_to_record(row: aiosqlite.Row) -> SOPRecord:
        draft = None
        if row["draft_module_json"]:
            draft = AOPDefinition.model_validate_json(row["draft_module_json"])
        issues: list[ValidationIssue] = []
        if row["validation_issues_json"]:
            issues = [
                ValidationIssue(**raw)
                for raw in json.loads(row["validation_issues_json"])
            ]
        return SOPRecord(
            id=row["id"],
            filename=row["filename"],
            content_type=row["content_type"],
            size=row["size"],
            storage_key=row["storage_key"],
            status=row["status"],
            canonical_md=row["canonical_md"],
            draft_module=draft,
            validation_issues=issues,
            promoted_module_name=row["promoted_module_name"],
            promoted_module_version=row["promoted_module_version"],
            owner_id=row["owner_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
