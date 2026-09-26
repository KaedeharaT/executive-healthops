"""Business progress from the existing goals; no second queue or state store."""
from dataclasses import dataclass
from datetime import timezone
from uuid import UUID
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal
from executive_health_ai.agent.post_checkup import is_care_goal
from executive_health_ai.ui import components as c, experience as ux


@dataclass(frozen=True)
class AssistantGroups:
    active: tuple
    attention: tuple
    recent: tuple


def _instant(value):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).timestamp() if value else float('-inf')


def project_assistant(goals):
    """Partition unique goal instances before applying the completed preview limit.

    Titles and reports are not identities. Prefer the latest snapshot if a caller
    supplies the same goal more than once, including across a state transition.
    """
    unique = {}
    for goal in goals:
        identity = str(goal.id)
        try:
            identity = UUID(identity).hex
        except ValueError:
            pass
        previous = unique.get(identity)
        rank = lambda g: (_instant(g.updated_at), g.status == 'COMPLETED')
        if previous is None or rank(goal) > rank(previous):
            unique[identity] = goal
    priorities = {'ESCALATED': 0, 'WAITING_MANAGER': 1, 'WAITING_DOCTOR': 2, 'RUNNING': 3}
    active = sorted((g for g in unique.values() if g.status in priorities),
                    key=lambda g: (priorities[g.status], -_instant(g.updated_at), str(g.id)))
    # Preserve existing recovery paths without mixing exceptional states into
    # either the four active states or completed work.
    attention = sorted((g for g in unique.values() if g.status in {'WAITING_INPUT', 'FAILED'}),
                       key=lambda g: (-_instant(g.updated_at), str(g.id)))
    recent = sorted((g for g in unique.values() if g.status == 'COMPLETED'),
                    key=lambda g: (-_instant(g.completed_at or g.updated_at), str(g.id)))[:3]
    return AssistantGroups(tuple(active), tuple(attention), tuple(recent))


def open_care(app, goal, origin='今日工作'):
    st.session_state['care-detail'] = str(goal.id)
    st.session_state['care-origin'] = origin
    app.request_navigation(surface='运营后台', ops_page='今日', rerun=False)


def assistant(app, people):
    from executive_health_ai.ui.pages.manager import care_activity
    care_activity.styles()
    with SessionLocal() as session:
        goals = [g for g in session.scalars(select(AgentGoal).order_by(AgentGoal.updated_at.desc())) if is_care_goal(g)]
    groups = project_assistant(goals)
    active, recent = groups.active, groups.recent
    pending = active + groups.attention
    st.subheader('健康管理助手')
    c.summary_strip([('正在运行', sum(g.status == 'RUNNING' for g in active)),
        ('等待我确认', sum(g.status in {'WAITING_MANAGER','WAITING_INPUT'} for g in pending)),
        ('等待医生', sum(g.status == 'WAITING_DOCTOR' for g in active)),
        ('需要优先处理',sum(g.status in {'ESCALATED','FAILED'} for g in pending)), ('最近完成', len(recent))])
    st.markdown('#### 活动流程')
    if not pending:
        st.caption('当前没有需要您处理的自动流程。')
    with st.container(key='assistant-active'):
        _cards(app, people, active)
    if groups.attention:
        st.markdown('#### 需要人工协助')
        with st.container(key='assistant-attention'):
            _cards(app, people, groups.attention)
    st.markdown('#### 最近完成')
    st.caption('按完成时间显示最近 3 条；每张卡片对应一次独立的报告管理流程。')
    with st.container(key='assistant-recent'):
        if recent:
            _cards(app, people, recent)
        else:
            st.caption('暂无已完成的自动流程。')


def _cards(app, people, goals):
    from executive_health_ai.ui.pages.manager import care_activity
    for index, goal in enumerate(goals):
        if index % 3 == 0:
            columns = st.columns(min(3, len(goals) - index))
        activity = care_activity.load(goal)
        with columns[index % 3], st.container(border=True, key=f'assistant-card-{goal.id}'):
            st.markdown('**'+app._member_display(people.get(goal.member_id))+' · 体检后健康管理**')
            report = (goal.context_json or {}).get('report') or {}
            st.caption('来源：' + (report.get('title') or '新体检报告'))
            if report.get('at'):
                st.caption('报告日期：' + str(report['at'])[:10])
            if goal.status == 'COMPLETED' and goal.completed_at:
                st.caption('完成时间：' + ux.local_time(goal.completed_at).strftime('%Y-%m-%d %H:%M'))
            st.markdown('**当前：'+activity.current+'**')
            st.caption('已完成')
            if activity.done:
                for work in activity.done[-3:]:
                    st.write('✓ '+work.title)
            else:
                st.caption('工作已启动，完成记录将随实际处理更新。')
            st.write('下一步：'+activity.next_action)
            if goal.status in {'WAITING_MANAGER','WAITING_INPUT','ESCALATED','FAILED'}:
                st.button('查看运行看板', key=f'assistant-open-{goal.id}', type='primary' if index==0 else 'secondary', on_click=open_care, args=(app,goal))
            else:
                st.caption('无需您操作')
                st.button('查看运行看板',key=f'assistant-progress-{goal.id}',on_click=open_care,args=(app,goal))


def progress(item):
    if item.source_type == 'post_checkup':
        return item.reason
    if item.status == '等待医生':
        return '已提交医学问题与依据'
    return {'task':'已明确执行安排','recheck':'已建立复查计划','service_request':'已接收服务安排',
        'risk_event':'已按现有规则核对数据','report_review':'已接收体检资料','consultation':'已建立会诊安排',
        'stage_review':'已汇集本阶段记录','intake_review':'已收到会员评估资料',
        'management_signal':'已汇集近期健康数据','automation_approval':'已准备后续安排'}.get(item.source_type, '已记录待处理事项')
