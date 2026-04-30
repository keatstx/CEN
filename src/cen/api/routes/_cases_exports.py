"""Case summary + packet-export endpoints.

Extracted from ``routes/cases.py`` per CLAUDE.md §4.9. Registered onto
the cases router via ``register_export_routes``.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from cen.api.dependencies import (
    get_artifact_store,
    get_current_user,
    get_session_store,
    get_storage_backend,
)
from cen.core.artifact_store import ArtifactStore
from cen.core.case_export import (
    build_case_packet_zip,
    case_summary_dict,
    render_case_summary_html,
)
from cen.core.exceptions import SessionNotFoundError
from cen.core.models import User
from cen.core.session_store import SessionStore
from cen.storage.base import StorageBackend


def register_export_routes(router: APIRouter) -> None:
    """Register the case summary + packet export endpoints."""

    @router.get("/{case_id}/summary")
    async def case_summary(
        case_id: str,
        format: str = Query(default="html", pattern="^(html|json)$"),
        store: SessionStore = Depends(get_session_store),
        artifact_store: ArtifactStore = Depends(get_artifact_store),
        user: User = Depends(get_current_user),
    ) -> Response:
        """Render the case as a printable summary. Format can be html
        (default — opens in a browser tab, save/print to PDF) or json
        (machine-readable structured data)."""
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        if session.owner_id is not None and session.owner_id != user.id:
            raise SessionNotFoundError(case_id)
        artifacts = await artifact_store.list_for_case(case_id, owner_id=user.id)

        if format == "json":
            payload = case_summary_dict(session, artifacts)
            return Response(
                content=json.dumps(payload, indent=2),
                media_type="application/json",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="case_{case_id}_summary.json"'
                    ),
                },
            )

        html_content = render_case_summary_html(session, artifacts)
        return Response(
            content=html_content,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "private, no-store"},
        )

    @router.get("/{case_id}/export")
    async def case_export(
        case_id: str,
        store: SessionStore = Depends(get_session_store),
        artifact_store: ArtifactStore = Depends(get_artifact_store),
        storage: StorageBackend = Depends(get_storage_backend),
        user: User = Depends(get_current_user),
    ) -> Response:
        """Bundle the case as a single ZIP packet containing summary.html,
        summary.json, and a documents/ folder with every uploaded file."""
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        if session.owner_id is not None and session.owner_id != user.id:
            raise SessionNotFoundError(case_id)

        artifacts = await artifact_store.list_for_case(case_id, owner_id=user.id)
        blobs: dict[str, bytes] = {}
        for a in artifacts:
            try:
                blobs[a.id] = await storage.read(a.storage_key)
            except FileNotFoundError:
                continue

        zip_bytes = build_case_packet_zip(session, artifacts, blobs)
        # Content-Disposition headers must be ASCII (latin-1).
        raw_name = session.name or case_id
        safe_name = "".join(
            c if (c.isascii() and c not in '/\\:*?"<>|') else "_"
            for c in raw_name
        ).strip("_ ") or case_id
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="case_{safe_name}.zip"',
                "Cache-Control": "private, no-store",
            },
        )
