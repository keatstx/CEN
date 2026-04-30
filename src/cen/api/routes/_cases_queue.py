"""Queue endpoint — bucketed cases for the Navigator Dashboard.

Two SQL queries (list owner's sessions + grouped audit MAX(timestamp))
plus a metrics count, then bucketing in memory. O(N) where N is the
navigator's case count. Registered onto the cases router via
``register_queue_routes``.

Per CLAUDE.md §4.9 file-size discipline, this lives in its own file.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from cen.api.dependencies import (
    get_audit_store,
    get_current_user,
    get_session_store,
)
from cen.core.audit_store import AuditStore
from cen.core.models import User
from cen.core.queue import BucketedQueue, bucket_cases
from cen.core.session_store import SessionStore


def register_queue_routes(router: APIRouter) -> None:
    """Register the GET /queue endpoint on the supplied router."""

    @router.get("/queue", response_model=BucketedQueue)
    async def get_case_queue(
        store: SessionStore = Depends(get_session_store),
        audit_store: AuditStore = Depends(get_audit_store),
        user: User = Depends(get_current_user),
    ) -> BucketedQueue:
        # 500 is the limit we already cap list_sessions at — covers
        # the typical navigator's 20-50 active cases by a wide margin.
        # Pagination is a follow-up if a navigator ever exceeds it.
        cases = await store.list_sessions(owner_id=user.id, limit=500)
        case_ids = [c.id for c in cases]

        last_activity = await audit_store.get_latest_event_at_for_cases(case_ids)

        now = datetime.now(timezone.utc)
        today_start_iso = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        approvals_today = await audit_store.count_events(
            case_ids=case_ids,
            node_type="APPROVAL",
            outcome="approved",
            since=today_start_iso,
        )

        return bucket_cases(
            cases=cases,
            last_activity_by_case=last_activity,
            approvals_today_count=approvals_today,
            now=now,
        )
