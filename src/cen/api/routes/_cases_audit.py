"""Audit-trail endpoints for cases.

Extracted from ``routes/cases.py`` per CLAUDE.md §4.9. Registered onto
the cases router via ``register_audit_routes``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from cen.api.dependencies import get_audit_store, get_session_store
from cen.core.audit_export import export_csv, export_json
from cen.core.audit_store import AuditStore
from cen.core.exceptions import SessionNotFoundError
from cen.core.models import AuditEntry, AuditVerification
from cen.core.session_store import SessionStore


def register_audit_routes(router: APIRouter) -> None:
    """Register the three audit endpoints on the supplied router."""

    @router.get("/{case_id}/audit", response_model=list[AuditEntry])
    async def get_audit_trail(
        case_id: str,
        node_type: Optional[str] = Query(default=None),
        outcome: Optional[str] = Query(default=None),
        start_time: Optional[str] = Query(default=None),
        end_time: Optional[str] = Query(default=None),
        limit: int = Query(default=500, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
        store: SessionStore = Depends(get_session_store),
        audit_store: AuditStore = Depends(get_audit_store),
    ) -> List[AuditEntry]:
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        return await audit_store.query(
            session_id=case_id,
            node_type=node_type,
            outcome=outcome,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )

    @router.get("/{case_id}/audit/verify", response_model=AuditVerification)
    async def verify_audit_trail(
        case_id: str,
        store: SessionStore = Depends(get_session_store),
        audit_store: AuditStore = Depends(get_audit_store),
    ) -> AuditVerification:
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        is_valid, last_verified_id, total_records = await audit_store.verify_chain(
            case_id
        )
        return AuditVerification(
            is_valid=is_valid,
            last_verified_id=last_verified_id,
            total_records=total_records,
            verified_at=datetime.now(timezone.utc).isoformat(),
        )

    @router.get("/{case_id}/audit/export")
    async def export_audit_trail(
        case_id: str,
        format: str = Query(default="json", pattern="^(json|csv)$"),
        node_type: Optional[str] = Query(default=None),
        outcome: Optional[str] = Query(default=None),
        start_time: Optional[str] = Query(default=None),
        end_time: Optional[str] = Query(default=None),
        limit: int = Query(default=500, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
        store: SessionStore = Depends(get_session_store),
        audit_store: AuditStore = Depends(get_audit_store),
    ) -> Response:
        session = await store.get(case_id)
        if session is None:
            raise SessionNotFoundError(case_id)
        entries = await audit_store.query(
            session_id=case_id,
            node_type=node_type,
            outcome=outcome,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            offset=offset,
        )
        if format == "csv":
            content = export_csv(entries)
            media_type = "text/csv"
            filename = f"audit_{case_id}.csv"
        else:
            content = export_json(entries)
            media_type = "application/json"
            filename = f"audit_{case_id}.json"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
