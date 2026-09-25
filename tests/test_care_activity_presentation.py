"""Business-visible progress must be grounded in existing execution records."""
from datetime import datetime, timezone
from types import SimpleNamespace as Record
from uuid import UUID
from sqlalchemy import select

from test_post_checkup_care_v1 import care, send_doctor, judge
from executive_health_ai.agent import post_checkup as flow
from executive_health_ai.models import AgentEvent, AgentRunTrace, DoctorReview
from executive_health_ai.ui.pages.manager.care_activity import project, entry_text


def presentation(session, goal):
    return project(goal, list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id == goal.id))),
        session.scalar(select(AgentEvent).where(AgentEvent.event_type == 'REPORT_UPLOADED')),
        session.get(DoctorReview, UUID(goal.context_json['review_id'])) if goal.context_json.get('review_id') else None)


def test_real_gate_records_entry_and_successful_work_without_raw_output(care):
    session, goal, _ = care
    event = session.scalar(select(AgentEvent).where(AgentEvent.event_type == 'REPORT_UPLOADED'))
    event.occurred_at = datetime(2026, 9, 25, 1, 16, tzinfo=timezone.utc)
    result = presentation(session, goal)
    labels = [work.title for work in result.done]
    assert result.started_at == event.occurred_at
    assert '2026-09-25' in entry_text(result)
    assert result.current == '等待您的确认'
    assert result.next_action == '确认 3 项健康变化'
    assert '确认后系统会自动继续' in result.after_confirmation
    assert '读取体检报告' in labels
    assert any('暂无匹配' in label for label in labels)
    assert not any('已提交责任医生' in label for label in labels)
    assert goal.status == 'WAITING_MANAGER'  # Projection never changes workflow.


def test_running_only_marks_successful_recorded_tools():
    at = datetime(2026, 9, 25)
    goal = Record(status='RUNNING', current_stage='ANALYZING', started_at=at,
                  context_json={'baseline': {'year': 2026}, 'findings': []})
    traces = [Record(action='tool_completed', status=status, tool_name=tool,
                     started_at=at, completed_at=at, result_summary='Trace UUID ToolCall secret')
              for tool, status in [('get_report', 'COMPLETED'), ('get_baseline', 'FAILED')]]
    result = project(goal, traces)
    assert [work.title for work in result.done] == ['读取体检报告']
    assert '正在工作' in result.headline
    assert '当前无需操作' in result.after_confirmation
    assert 'Trace' not in str(result) and 'secret' not in str(result)


def test_doctor_wait_resume_and_completed_output_follow_same_goal(care):
    session, goal, supervisor = care
    identity = goal.id
    send_doctor(session, goal, supervisor)
    waiting = presentation(session, goal)
    assert waiting.current == '等待医生判断'
    assert waiting.next_action == '医生提交后自动继续'
    assert any(work.title == '已提交责任医生判断' for work in waiting.done)
    judge(session, goal)
    approval = presentation(session, goal)
    assert approval.next_action == '确认 3 项后续安排'
    assert any('已收到医生判断' in work.title for work in approval.done)
    assert not any('正式建立后续安排' in work.title for work in approval.done)
    flow.approve_actions(supervisor, session, goal, actions=goal.context_json['actions'],
                        actor='王健管', role='HEALTH_MANAGER')
    completed = presentation(session, goal)
    assert goal.id == identity
    assert completed.current == '本次管理已完成'
    assert goal.context_json['next_node']['title'] in completed.next_action
    assert any('正式建立后续安排' in work.title for work in completed.done)
    assert any('完成本次自动管理' in work.title for work in completed.done)


def test_missing_records_do_not_invent_completed_work():
    goal = Record(status='WAITING_INPUT', current_stage='WAITING_MANAGER_REVIEW',
                  started_at=None, context_json={})
    result = project(goal)
    assert not result.done
    assert '人工协助' in result.headline
    assert entry_text(result) == '收到新的体检报告'
