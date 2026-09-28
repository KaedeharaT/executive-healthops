"""Business progress from the existing goals; no second queue or state store."""
from dataclasses import dataclass
from datetime import timezone
from html import escape
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
    completed: tuple


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
    priorities = {'ESCALATED': 0, 'WAITING_MANAGER': 1, 'WAITING_DOCTOR': 2, 'RUNNING': 3, 'PROCESSING': 3}
    active = sorted((g for g in unique.values() if g.status in priorities),
                    key=lambda g: (priorities[g.status], -_instant(g.updated_at), str(g.id)))
    # Preserve existing recovery paths without mixing exceptional states into
    # either the four active states or completed work.
    attention = sorted((g for g in unique.values() if g.status in {'WAITING_INPUT', 'FAILED'}),
                       key=lambda g: (-_instant(g.updated_at), str(g.id)))
    recent = sorted((g for g in unique.values() if g.status == 'COMPLETED'),
                    key=lambda g: (-_instant(g.completed_at or g.updated_at), str(g.id)))
    return AssistantGroups(tuple(active), tuple(attention), tuple(recent[:5]), tuple(recent))


def open_care(app, goal, origin='今日工作'):
    st.session_state.pop('today-detail', None)
    if getattr(goal,'goal_type',None)=='PROFILE_INTAKE':
        from executive_health_ai.ui.pages.manager.profile_intake import open_board
        open_board(app,goal,origin=origin)
        return
    st.session_state['care-detail'] = str(goal.id)
    st.session_state['care-origin'] = origin
    app.request_navigation(surface='运营后台', ops_page='今日', rerun=False)


def assistant(app, people):
    from executive_health_ai.ui.pages.manager import care_activity
    care_activity.styles()
    with SessionLocal() as session:
        from executive_health_ai.services.member_archive import active_ids
        goals = [g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id.in_(active_ids())).order_by(AgentGoal.updated_at.desc())) if is_care_goal(g) or g.goal_type == "PROFILE_INTAKE"]
    groups = project_assistant(goals)
    active, recent = groups.active, groups.recent
    pending = active + groups.attention
    st.subheader('健康管理助手')
    st.caption(f'正在运行 {sum(g.status in {"RUNNING","PROCESSING"} for g in active)} · 等待我确认 {sum(g.status in {"WAITING_MANAGER","WAITING_INPUT"} for g in pending)}')
    st.caption(f'等待医生 {sum(g.status=="WAITING_DOCTOR" for g in active)} · 最近完成 {len(groups.completed)}')
    if not pending:st.caption('当前没有需要您处理的自动流程。')
    for goal in pending[:3]:
        st.caption(app._member_display(people.get(goal.member_id))+' · '+ux.business_text(goal.next_action))
    if recent:st.caption('最近完成：'+app._member_display(people.get(recent[0].member_id))+' · '+completed_values(recent[0],'')[2])
    with st.expander('自动整理记录'):
        available=list(pending)+list(groups.completed)
        if available:
            goal=st.selectbox('选择处理记录',available,format_func=lambda g:app._member_display(people.get(g.member_id))+' · '+('资料导入' if g.goal_type=='PROFILE_INTAKE' else '体检后管理')+' · '+ux.when(g.updated_at),key='assistant-history-choice')
            st.button('查看完整运行',key='assistant-open',on_click=open_care,args=(app,goal))
        else:st.caption('上传资料后，将在会员健康档案中开始自动整理。')


def completed_values(goal, member):
    """Short history cells, retaining the real report date and actual outcome."""
    ctx = goal.context_json or {}
    if getattr(goal,'goal_type',None) == 'PROFILE_INTAKE':
        from executive_health_ai.services.profile_ingestion import TYPES
        return (ux.local_time(goal.completed_at or goal.updated_at).strftime('%Y-%m-%d %H:%M'), member, '健康资料导入', TYPES[ctx['document_type']],
            ctx.get('source_date') or '未注明', '初评资料已核对并提交' if ctx.get('intake_submitted') else '已更新健康档案', goal.next_action)
    report = ctx.get('report') or {}
    at = goal.completed_at or goal.updated_at
    return (ux.local_time(at).strftime('%Y-%m-%d %H:%M') if at else '—', member,
            '体检后健康管理', '体检报告', str(report.get('at') or '')[:10] or '未记录',
            '后续安排已建立' if any((ctx.get('created') or {}).values()) else '查看完成记录',
            (ctx.get('next_node') or {}).get('title') or '暂无后续节点')


def progress(item):
    if item.source_type in {'post_checkup','profile_intake'}:
        return item.reason
    if item.status == '等待医生':
        return '已提交医学问题与依据'
    return {'task':'已明确执行安排','recheck':'已建立复查计划','service_request':'已接收服务安排',
        'risk_event':'已按现有规则核对数据','report_review':'已接收体检资料','consultation':'已建立会诊安排',
        'stage_review':'已汇集本阶段记录','intake_review':'已收到会员评估资料',
        'management_signal':'已汇集近期健康数据','automation_approval':'已准备后续安排'}.get(item.source_type, '已记录待处理事项')
