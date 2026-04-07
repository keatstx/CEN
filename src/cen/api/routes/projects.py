"""Project CRUD endpoints.

A Project is the top-level container for one patient (or matter).
Multiple sessions/cases run under a Project, sharing demographics and
uploaded documents.

v1 exposes basic CRUD; the project picker UI lands in step 4 of the
foundation roadmap. New cases auto-attach to a default project if none
is specified — see sessions.create_session.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from cen.api.dependencies import get_project_store
from cen.core.models import Project, ProjectCreate, ProjectUpdate
from cen.core.project_store import ProjectStore

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=Project, status_code=201)
async def create_project(
    body: ProjectCreate,
    store: ProjectStore = Depends(get_project_store),
) -> Project:
    return await store.create(name=body.name, description=body.description)


@router.get("", response_model=list[Project])
async def list_projects(
    limit: int = Query(default=50, ge=1, le=500),
    store: ProjectStore = Depends(get_project_store),
) -> List[Project]:
    return await store.list_projects(limit=limit)


@router.get("/{project_id}", response_model=Project)
async def get_project(
    project_id: str,
    store: ProjectStore = Depends(get_project_store),
) -> Project:
    project = await store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    store: ProjectStore = Depends(get_project_store),
) -> Project:
    updated = await store.update(
        project_id, name=body.name, description=body.description
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return updated


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: str,
    store: ProjectStore = Depends(get_project_store),
) -> None:
    deleted = await store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
