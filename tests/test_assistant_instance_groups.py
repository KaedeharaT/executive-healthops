"""Assistant cards are instances, not titles, and completion is a separate lane."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from executive_health_ai.ui.pages.manager.assistant import project_assistant


def goal(identity, status='COMPLETED', day=1, **overrides):
    at = datetime(2026, 9, day, tzinfo=timezone.utc)
    return SimpleNamespace(**(dict(id=identity, status=status, updated_at=at,
        completed_at=at if status == 'COMPLETED' else None,
        title='Demo Executive A · 体检后健康管理') | overrides))


def test_repeated_instance_is_counted_once_but_identical_titles_are_preserved():
    first, second = goal('first'), goal('second')
    groups = project_assistant([first, second, first, second])
    assert {g.id for g in groups.recent} == {'first', 'second'}
    assert len(groups.recent) == 2
    assert not groups.active


@pytest.mark.parametrize('reverse', [False, True])
def test_latest_snapshot_partitions_before_dedup_and_limit(reverse):
    old = goal('same', 'WAITING_MANAGER', 1)
    complete = goal('same', 'COMPLETED', 2)
    rows = [old, complete]
    groups = project_assistant(rows[::-1] if reverse else rows)
    assert not groups.active
    assert groups.recent == (complete,)
    assert old.status == 'WAITING_MANAGER'  # Read-only projection.


def test_uuid_representations_are_the_same_business_identity():
    identity = UUID('452c77dd-29dd-40b4-9527-217759ecf649')
    groups = project_assistant([goal(identity), goal(identity.hex), goal(str(identity))])
    assert len(groups.recent) == 1


def test_recent_has_three_latest_completions_not_latest_audit_updates():
    rows = [goal(str(day), day=day) for day in range(1, 6)]
    rows[0].updated_at += timedelta(days=25)
    groups = project_assistant(rows + [rows[-1]])
    assert [g.id for g in groups.recent] == ['5', '4', '3']


def test_all_four_active_states_stay_separate_from_completed_and_recovery():
    states = ['RUNNING', 'WAITING_MANAGER', 'WAITING_DOCTOR', 'ESCALATED',
              'COMPLETED', 'WAITING_INPUT', 'FAILED', 'CANCELLED']
    rows = [goal(state, state) for state in states]
    groups = project_assistant(rows + rows)
    assert {g.status for g in groups.active} == set(states[:4])
    assert {g.status for g in groups.attention} == {'WAITING_INPUT', 'FAILED'}
    assert [g.status for g in groups.recent] == ['COMPLETED']
    displayed = groups.active + groups.attention + groups.recent
    assert len({g.id for g in displayed}) == len(displayed)


def test_missing_completion_time_uses_updated_time_without_timezone_mismatch():
    first = goal('first', completed_at=None)
    second = goal('second', day=2, completed_at=datetime(2026, 9, 2))
    assert project_assistant([first, second]).recent == (second, first)


def test_empty_groups_remain_empty():
    groups = project_assistant([])
    assert not (groups.active or groups.attention or groups.recent)
