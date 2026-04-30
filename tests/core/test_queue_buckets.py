"""Pure-function tests for the dashboard bucketing logic.

The bucket rules are the contract — these tests guard mutual
exclusion, the idle override, and the due-soon decoration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cen.core.models import Session, SessionStatus
from cen.core.queue import bucket_cases


_NOW = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


def _case(
    status: SessionStatus,
    *,
    case_id: str = "c1",
    name: str = "Case 1",
    module_name: str = "charity_care_navigator",
    pending_node: str | None = None,
    due_at: str | None = None,
    updated_offset_days: float = 0,
    created_offset_days: float = 0,
) -> Session:
    updated = _NOW - timedelta(days=updated_offset_days)
    created = _NOW - timedelta(days=created_offset_days)
    return Session(
        id=case_id,
        module_name=module_name,
        name=name,
        status=status,
        pending_node=pending_node,
        due_at=due_at,
        owner_id="user1",
        created_at=created.isoformat(),
        updated_at=updated.isoformat(),
    )


# ── Mutual exclusion ────────────────────────────────────────────────


def test_awaiting_input_lands_in_needs_attention():
    queue = bucket_cases(
        cases=[_case(SessionStatus.AWAITING_INPUT, pending_node="step1")],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.needs_attention) == 1
    assert queue.in_progress == []
    assert queue.idle == []


def test_awaiting_approval_lands_in_needs_attention():
    queue = bucket_cases(
        cases=[_case(SessionStatus.AWAITING_APPROVAL, pending_node="gate")],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.needs_attention) == 1


def test_awaiting_external_lands_in_waiting_external():
    queue = bucket_cases(
        cases=[_case(SessionStatus.AWAITING_EXTERNAL, pending_node="hospital")],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.waiting_external) == 1
    assert queue.needs_attention == []


def test_active_lands_in_in_progress():
    queue = bucket_cases(
        cases=[_case(SessionStatus.ACTIVE)],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.in_progress) == 1


def test_completed_today_lands_in_done_today():
    queue = bucket_cases(
        cases=[_case(SessionStatus.COMPLETED, updated_offset_days=0)],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.done_today) == 1


def test_completed_yesterday_is_hidden():
    queue = bucket_cases(
        cases=[_case(SessionStatus.COMPLETED, updated_offset_days=1.5)],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.done_today == []
    assert queue.idle == []  # COMPLETED is terminal — never idle


def test_failed_lands_in_failed():
    queue = bucket_cases(
        cases=[_case(SessionStatus.FAILED)],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.failed) == 1


# ── Idle override ───────────────────────────────────────────────────


def test_idle_overrides_in_progress():
    """An ACTIVE case with no recent activity should land in idle,
    not in_progress."""
    case = _case(SessionStatus.ACTIVE, updated_offset_days=5)
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={
            "c1": (_NOW - timedelta(days=5)).isoformat(),
        },
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.idle) == 1
    assert queue.in_progress == []
    assert queue.idle[0].days_idle == 5


def test_idle_overrides_needs_attention():
    """An AWAITING_INPUT case stale 5 days lands in idle."""
    case = _case(
        SessionStatus.AWAITING_INPUT,
        pending_node="step1",
        updated_offset_days=5,
    )
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={
            "c1": (_NOW - timedelta(days=5)).isoformat(),
        },
        approvals_today_count=0,
        now=_NOW,
    )
    assert len(queue.idle) == 1
    assert queue.needs_attention == []


def test_idle_threshold_boundary():
    """Exactly at the threshold (3 days) → idle. Below → needs_attention."""
    today_active = _case(
        SessionStatus.AWAITING_INPUT,
        case_id="today",
        pending_node="x",
        updated_offset_days=2,
    )
    threshold = _case(
        SessionStatus.AWAITING_INPUT,
        case_id="three",
        pending_node="x",
        updated_offset_days=3.5,
    )
    queue = bucket_cases(
        cases=[today_active, threshold],
        last_activity_by_case={
            "today": (_NOW - timedelta(days=2)).isoformat(),
            "three": (_NOW - timedelta(days=3.5)).isoformat(),
        },
        approvals_today_count=0,
        now=_NOW,
    )
    assert {c.id for c in queue.needs_attention} == {"today"}
    assert {c.id for c in queue.idle} == {"three"}


def test_completed_never_marked_idle_even_if_old():
    case = _case(SessionStatus.COMPLETED, updated_offset_days=30)
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={"c1": (_NOW - timedelta(days=30)).isoformat()},
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.idle == []
    assert queue.done_today == []  # not today either — it's hidden


# ── Due-soon decorations ────────────────────────────────────────────


def test_due_soon_decoration_within_threshold():
    case = _case(
        SessionStatus.AWAITING_INPUT,
        pending_node="x",
        due_at=(_NOW + timedelta(days=3)).isoformat(),
    )
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.needs_attention[0].is_due_soon is True
    assert queue.needs_attention[0].is_overdue is False


def test_overdue_decoration():
    case = _case(
        SessionStatus.AWAITING_INPUT,
        pending_node="x",
        due_at=(_NOW - timedelta(days=2)).isoformat(),
    )
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.needs_attention[0].is_overdue is True
    assert queue.needs_attention[0].is_due_soon is False


def test_no_due_at_no_decorations():
    case = _case(SessionStatus.AWAITING_INPUT, pending_node="x", due_at=None)
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.needs_attention[0].is_due_soon is False
    assert queue.needs_attention[0].is_overdue is False


# ── Sort ordering within a bucket ───────────────────────────────────


def test_overdue_sorts_before_due_soon():
    overdue = _case(
        SessionStatus.AWAITING_INPUT,
        case_id="overdue",
        pending_node="x",
        due_at=(_NOW - timedelta(days=1)).isoformat(),
    )
    due_soon = _case(
        SessionStatus.AWAITING_INPUT,
        case_id="duesoon",
        pending_node="x",
        due_at=(_NOW + timedelta(days=2)).isoformat(),
    )
    no_due = _case(
        SessionStatus.AWAITING_INPUT,
        case_id="nodue",
        pending_node="x",
    )
    queue = bucket_cases(
        cases=[no_due, due_soon, overdue],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert [c.id for c in queue.needs_attention] == ["overdue", "duesoon", "nodue"]


# ── Metrics ────────────────────────────────────────────────────────


def test_metrics_count_correctly():
    cases = [
        _case(SessionStatus.AWAITING_INPUT, case_id="a", pending_node="x", created_offset_days=0),  # opened today, open
        _case(SessionStatus.COMPLETED, case_id="b", updated_offset_days=0, created_offset_days=2),  # completed today
        _case(SessionStatus.AWAITING_APPROVAL, case_id="c", pending_node="g", created_offset_days=10),  # open
        _case(SessionStatus.FAILED, case_id="d", created_offset_days=5),  # failed (not open)
    ]
    queue = bucket_cases(
        cases=cases,
        last_activity_by_case={},
        approvals_today_count=4,
        now=_NOW,
    )
    assert queue.metrics.opened_today == 1
    assert queue.metrics.completed_today == 1
    assert queue.metrics.approvals_today == 4
    assert queue.metrics.open_cases == 2  # a, c (b is completed, d is failed)


def test_empty_input_returns_empty_queue():
    queue = bucket_cases(
        cases=[],
        last_activity_by_case={},
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.needs_attention == []
    assert queue.metrics.opened_today == 0
    assert queue.metrics.open_cases == 0


def test_last_activity_falls_back_to_updated_at():
    """When a case has no audit entries, last_activity_at uses
    updated_at — typical for a freshly-created case."""
    case = _case(SessionStatus.ACTIVE, updated_offset_days=1)
    queue = bucket_cases(
        cases=[case],
        last_activity_by_case={},  # no audit entry
        approvals_today_count=0,
        now=_NOW,
    )
    assert queue.in_progress[0].last_activity_at == case.updated_at
