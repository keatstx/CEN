"""Navigator-dashboard queue: bucket cases by attention-state.

Pure functions only — given a list of sessions, a map of last-activity
timestamps, and "now", returns a ``BucketedQueue`` with cases sorted
into mutually-exclusive buckets and decorated with due-soon /
overdue / days-idle hints.

The queue endpoint (``api/routes/_cases_queue.py``) is the only
consumer. Splitting bucketing into a pure function keeps the rules
testable in isolation and the endpoint thin.

Buckets (mutually exclusive — a case lives in exactly one):

- ``needs_attention`` — AWAITING_INPUT or AWAITING_APPROVAL
- ``waiting_external`` — AWAITING_EXTERNAL (handed off, awaiting
  third-party response)
- ``in_progress``     — ACTIVE (rare; engine usually pauses immediately)
- ``idle``            — non-terminal status with last activity older
  than the idle threshold (overrides ``in_progress`` /
  ``waiting_external`` / ``needs_attention``)
- ``done_today``      — COMPLETED with updated_at on today's date
- ``failed``          — FAILED

Cards in any non-terminal bucket carry ``is_due_soon`` /
``is_overdue`` decorations from the case's ``due_at`` field. Card
ordering within each bucket: due-soonest first when due_at is set,
otherwise by last activity descending (most recent on top).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from cen.core.models import Session, SessionStatus


_NON_TERMINAL_STATUSES = {
    SessionStatus.ACTIVE,
    SessionStatus.AWAITING_APPROVAL,
    SessionStatus.AWAITING_INPUT,
    SessionStatus.AWAITING_EXTERNAL,
}

_NEEDS_ATTENTION_STATUSES = {
    SessionStatus.AWAITING_INPUT,
    SessionStatus.AWAITING_APPROVAL,
}


class QueueCase(BaseModel):
    """One row on the dashboard. Minimal projection of Session — just
    what the cards need so we don't ship unscrubbed context to the
    frontend (Non-Negotiable #1)."""

    id: str
    name: str
    module_name: str
    status: SessionStatus
    pending_node: Optional[str] = None
    due_at: Optional[str] = None
    last_activity_at: str
    is_overdue: bool = False
    is_due_soon: bool = False
    days_idle: int = 0


class QueueMetrics(BaseModel):
    opened_today: int = 0
    approvals_today: int = 0
    completed_today: int = 0
    open_cases: int = 0


class BucketedQueue(BaseModel):
    needs_attention: List[QueueCase] = Field(default_factory=list)
    waiting_external: List[QueueCase] = Field(default_factory=list)
    in_progress: List[QueueCase] = Field(default_factory=list)
    idle: List[QueueCase] = Field(default_factory=list)
    done_today: List[QueueCase] = Field(default_factory=list)
    failed: List[QueueCase] = Field(default_factory=list)
    metrics: QueueMetrics = Field(default_factory=QueueMetrics)


def bucket_cases(
    *,
    cases: List[Session],
    last_activity_by_case: dict[str, str],
    approvals_today_count: int,
    now: datetime,
    idle_threshold_days: int = 3,
    due_soon_threshold_days: int = 7,
) -> BucketedQueue:
    """Bucket cases for the navigator dashboard.

    ``last_activity_by_case`` maps case_id → ISO timestamp of the most
    recent audit event. Falls back to ``Session.updated_at`` when a
    case has no audit entries (e.g., freshly created).
    """
    queue = BucketedQueue()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    opened_today = 0
    completed_today = 0
    open_cases = 0

    for case in cases:
        last_activity = last_activity_by_case.get(case.id) or case.updated_at
        days_idle = _days_since(last_activity, now)

        decorated = QueueCase(
            id=case.id,
            name=case.name or case.module_name,
            module_name=case.module_name,
            status=case.status,
            pending_node=case.pending_node,
            due_at=case.due_at,
            last_activity_at=last_activity,
            is_overdue=_is_overdue(case.due_at, now),
            is_due_soon=_is_due_soon(case.due_at, now, due_soon_threshold_days),
            days_idle=days_idle,
        )

        # Metrics counted across all cases (independent of bucket).
        if _is_today(case.created_at, today_start):
            opened_today += 1
        if (
            case.status == SessionStatus.COMPLETED
            and _is_today(case.updated_at, today_start)
        ):
            completed_today += 1
        if case.status in _NON_TERMINAL_STATUSES:
            open_cases += 1

        # Bucket assignment. Idle wins over any non-terminal bucket
        # because a case the navigator forgot about is more urgent to
        # surface than one they're actively driving.
        is_idle = (
            case.status in _NON_TERMINAL_STATUSES
            and days_idle >= idle_threshold_days
        )
        if case.status == SessionStatus.FAILED:
            queue.failed.append(decorated)
        elif (
            case.status == SessionStatus.COMPLETED
            and _is_today(case.updated_at, today_start)
        ):
            queue.done_today.append(decorated)
        elif is_idle:
            queue.idle.append(decorated)
        elif case.status in _NEEDS_ATTENTION_STATUSES:
            queue.needs_attention.append(decorated)
        elif case.status == SessionStatus.AWAITING_EXTERNAL:
            queue.waiting_external.append(decorated)
        elif case.status == SessionStatus.ACTIVE:
            queue.in_progress.append(decorated)
        # COMPLETED but not today: hidden from the dashboard. Use the
        # full case list to find it.

    # Sort each bucket: due-soonest first when due_at is set, then by
    # last activity descending. Failed bucket sorts by recency only.
    for bucket in (
        queue.needs_attention,
        queue.waiting_external,
        queue.in_progress,
        queue.idle,
    ):
        bucket.sort(key=_sort_key_attention)
    queue.done_today.sort(key=lambda c: c.last_activity_at, reverse=True)
    queue.failed.sort(key=lambda c: c.last_activity_at, reverse=True)

    queue.metrics = QueueMetrics(
        opened_today=opened_today,
        approvals_today=approvals_today_count,
        completed_today=completed_today,
        open_cases=open_cases,
    )
    return queue


# ── Helpers ──────────────────────────────────────────────────────────


def _sort_key_attention(c: QueueCase) -> tuple:
    """Sort key: due_at first (overdue → due soon → no due date),
    then most-recent activity within each tier."""
    if c.is_overdue:
        tier = 0
    elif c.is_due_soon:
        tier = 1
    elif c.due_at:
        tier = 2
    else:
        tier = 3
    # Negate last_activity timestamp lexicographically by inverting
    # via a recency tuple: ISO timestamps sort lex-equal to chrono,
    # so we use a high-to-low ordering by negating with a sentinel.
    return (tier, c.due_at or "9999", -_iso_to_epoch(c.last_activity_at))


def _iso_to_epoch(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0


def _days_since(iso: str, now: datetime) -> int:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt).days)
    except (ValueError, TypeError):
        return 0


def _is_today(iso: str, today_start: datetime) -> bool:
    if not iso:
        return False
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= today_start
    except (ValueError, TypeError):
        return False


def _is_overdue(due_at: Optional[str], now: datetime) -> bool:
    if not due_at:
        return False
    try:
        dt = datetime.fromisoformat(due_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt < now
    except (ValueError, TypeError):
        return False


def _is_due_soon(
    due_at: Optional[str], now: datetime, threshold_days: int
) -> bool:
    if not due_at:
        return False
    try:
        dt = datetime.fromisoformat(due_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt < now:
            return False  # overdue is its own state, not "due soon"
        return dt <= now + timedelta(days=threshold_days)
    except (ValueError, TypeError):
        return False
