"""SQLite-backed metadata store for case artifacts (uploaded files).

The actual file bytes live in a StorageBackend (see cen.storage). This
store tracks the database row that links each blob to a case, project,
node, and owner.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from cen.core.models import Artifact


class ArtifactStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS case_artifacts (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                project_id TEXT,
                node_id TEXT,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                storage_key TEXT NOT NULL,
                owner_id TEXT,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_case_artifacts_case_id ON case_artifacts(case_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_case_artifacts_project_id ON case_artifacts(project_id)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_case_artifacts_owner_id ON case_artifacts(owner_id)"
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(
        self,
        *,
        case_id: str,
        filename: str,
        content_type: str,
        size: int,
        storage_key: str,
        project_id: Optional[str] = None,
        node_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Artifact:
        now = datetime.now(timezone.utc).isoformat()
        artifact = Artifact(
            id=uuid.uuid4().hex,
            case_id=case_id,
            project_id=project_id,
            node_id=node_id,
            filename=filename,
            content_type=content_type,
            size=size,
            storage_key=storage_key,
            owner_id=owner_id,
            uploaded_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO case_artifacts (
                id, case_id, project_id, node_id, filename,
                content_type, size, storage_key, owner_id, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.id,
                artifact.case_id,
                artifact.project_id,
                artifact.node_id,
                artifact.filename,
                artifact.content_type,
                artifact.size,
                artifact.storage_key,
                artifact.owner_id,
                artifact.uploaded_at,
            ),
        )
        await self._db.commit()
        return artifact

    async def get(self, artifact_id: str) -> Artifact | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM case_artifacts WHERE id = ?", (artifact_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_artifact(row)

    async def list_for_case(
        self, case_id: str, owner_id: str | None = None
    ) -> list[Artifact]:
        assert self._db is not None
        if owner_id is None:
            query = (
                "SELECT * FROM case_artifacts WHERE case_id = ? "
                "ORDER BY uploaded_at DESC"
            )
            params: tuple = (case_id,)
        else:
            query = (
                "SELECT * FROM case_artifacts WHERE case_id = ? AND owner_id = ? "
                "ORDER BY uploaded_at DESC"
            )
            params = (case_id, owner_id)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_artifact(row) for row in rows]

    async def delete(self, artifact_id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM case_artifacts WHERE id = ?", (artifact_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    @staticmethod
    def _row_to_artifact(row: aiosqlite.Row) -> Artifact:
        return Artifact(
            id=row["id"],
            case_id=row["case_id"],
            project_id=row["project_id"],
            node_id=row["node_id"],
            filename=row["filename"],
            content_type=row["content_type"],
            size=row["size"],
            storage_key=row["storage_key"],
            owner_id=row["owner_id"],
            uploaded_at=row["uploaded_at"],
        )
