"""SQLite-backed project persistence via aiosqlite.

A Project is a top-level container for one patient (or matter). One or
more Sessions/Cases run under a Project, sharing demographics and
uploaded documents.

v1 stores projects but does not yet expose them in the UI — every new
case auto-attaches to a default project per owner. The full project
picker UI lands in step 4 of the foundation roadmap.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

from cen.core.models import Project


_DEFAULT_PROJECT_NAME = "Default"


class ProjectStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                owner_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects(owner_id)"
        )
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(
        self,
        name: str,
        description: str = "",
        owner_id: str | None = None,
    ) -> Project:
        now = datetime.now(timezone.utc).isoformat()
        project = Project(
            id=uuid.uuid4().hex,
            name=name,
            description=description,
            owner_id=owner_id,
            created_at=now,
            updated_at=now,
        )
        assert self._db is not None
        await self._db.execute(
            """
            INSERT INTO projects (id, name, description, owner_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project.id,
                project.name,
                project.description,
                project.owner_id,
                project.created_at,
                project.updated_at,
            ),
        )
        await self._db.commit()
        return project

    async def get(self, project_id: str) -> Project | None:
        assert self._db is not None
        async with self._db.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    async def update(
        self,
        project_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Project | None:
        existing = await self.get(project_id)
        if existing is None:
            return None
        updates: list[tuple[str, str]] = []
        params: list = []
        if name is not None:
            updates.append(("name = ?", name))
        if description is not None:
            updates.append(("description = ?", description))
        if not updates:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        set_clauses = [u[0] for u in updates] + ["updated_at = ?"]
        params = [u[1] for u in updates] + [now, project_id]
        assert self._db is not None
        await self._db.execute(
            f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?",
            params,
        )
        await self._db.commit()
        return await self.get(project_id)

    async def list_projects(
        self,
        owner_id: str | None = None,
        limit: int = 50,
    ) -> list[Project]:
        assert self._db is not None
        if owner_id is not None:
            query = (
                "SELECT * FROM projects WHERE owner_id = ? "
                "ORDER BY updated_at DESC LIMIT ?"
            )
            params: tuple = (owner_id, limit)
        else:
            query = "SELECT * FROM projects ORDER BY updated_at DESC LIMIT ?"
            params = (limit,)
        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_project(row) for row in rows]

    async def delete(self, project_id: str) -> bool:
        assert self._db is not None
        cursor = await self._db.execute(
            "DELETE FROM projects WHERE id = ?", (project_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def get_or_create_default(self, owner_id: str | None) -> Project:
        """Return the owner's default project, creating one if it doesn't exist.

        Used when a new case is created without an explicit project_id —
        every case must belong to *some* project, even before the project
        picker UI lands.
        """
        assert self._db is not None
        if owner_id is None:
            # Single shared default for the unauthenticated v1 path.
            async with self._db.execute(
                "SELECT * FROM projects WHERE owner_id IS NULL AND name = ? "
                "ORDER BY created_at ASC LIMIT 1",
                (_DEFAULT_PROJECT_NAME,),
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with self._db.execute(
                "SELECT * FROM projects WHERE owner_id = ? AND name = ? "
                "ORDER BY created_at ASC LIMIT 1",
                (owner_id, _DEFAULT_PROJECT_NAME),
            ) as cursor:
                row = await cursor.fetchone()
        if row is not None:
            return self._row_to_project(row)
        return await self.create(
            name=_DEFAULT_PROJECT_NAME,
            description="Auto-created default project for cases without an explicit project.",
            owner_id=owner_id,
        )

    @staticmethod
    def _row_to_project(row: aiosqlite.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            owner_id=row["owner_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
