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
    priorities = {'ESCALATED': 0, 'WAITING_MANAGER': 1, 'WAITING_DOCTOR': 2, 'RUNNING': 3}
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
        open_board(app,goal)
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
    with st.container(key='soft-assistant-status'):
        st.subheader('健康管理助手')
        c.summary_strip([('正在运行', sum(g.status == 'RUNNING' for g in active)),
            ('等待我确认', sum(g.status in {'WAITING_MANAGER','WAITING_INPUT'} for g in pending)),
            ('等待医生', sum(g.status == 'WAITING_DOCTOR' for g in active)),
            ('需要优先处理',sum(g.status in {'ESCALATED','FAILED'} for g in pending)), ('最近完成', len(recent))],
            anchors={'最近完成': 'assistant-recent'})
    st.markdown('#### 活动流程')
    if not pending:
        st.caption('当前没有需要您处理的自动流程。')
        if recent:
            st.caption('最近完成：' + ' · '.join(completed_values(recent[0], app._member_display(people.get(recent[0].member_id)))[1:3]))
            st.button('查看最近运行', key='assistant-latest', on_click=open_care, args=(app, recent[0]))
        else:
            st.caption('最近完成：暂无已完成的自动流程。')
            st.button('查看最近运行', key='assistant-latest', disabled=True, help='尚无可查看的运行记录。')
    with st.container(key='assistant-active'):
        _cards(app, people, active[:3])
        if len(active) > 3:
            st.caption(f'共 {len(active)} 条活动流程；其余流程可在工作事项或对应会员的自动跟进中查看。')
    if groups.attention:
        st.markdown('#### 需要人工协助')
        with st.container(key='assistant-attention'):
            _cards(app, people, groups.attention)
    st.subheader('最近完成', anchor='assistant-recent')
    with st.container(key='assistant-recent'):
        show_all = st.session_state.get('assistant-history-all', False)
        st.caption(f'共 {len(groups.completed)} 次完成记录 · 按完成时间倒序' if show_all else '最近 5 条 · 按完成时间倒序')
        if groups.completed:
            visible = recent
            if show_all:
                pages = max(1, (len(groups.completed) + 19) // 20)
                page = st.number_input('历史页码', min_value=1, max_value=pages, value=1) if pages > 1 else 1
                visible = groups.completed[(page-1)*20:page*20]
            _completed_rows(app, people, visible)
            st.button('收起历史' if show_all else '查看全部历史', key='assistant-history-toggle',
                      on_click=_toggle_history)
        else:
            st.caption('暂无已完成的自动流程。')


def _toggle_history():
    st.session_state['assistant-history-all'] = not st.session_state.get('assistant-history-all', False)


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


def _completed_rows(app, people, goals):
    # Native buttons preserve keyboard interaction and bind directly to each Goal.
    # Completed history never loads or repeats the full activity timeline.
    st.markdown('''<style>
    .st-key-assistant-recent [class*="st-key-completed-row-"] {border-bottom:1px solid #e5eaf0;padding:4px 0;}
    .st-key-assistant-recent [data-testid="stHorizontalBlock"] {gap:12px;flex-wrap:nowrap;}
    .st-key-assistant-recent [data-testid="stColumn"] {min-width:0!important;}
    .assistant-history-cell {font-size:13px;line-height:1.5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
    .assistant-history-head {color:#64748b;font-size:12px;font-weight:600;}
    .st-key-assistant-recent button {min-height:30px;padding:2px 6px;white-space:nowrap;}
    .st-key-assistant-recent button p {white-space:nowrap;}
    </style>''', unsafe_allow_html=True)
    widths = [1.65, 1.6, 1.5, .85, 1.05, 1.4, 2.25, .75]
    with st.container(key='completed-header'):
        for col, title in zip(st.columns(widths, vertical_alignment='center'),
                              ('完成时间', '会员', '流程', '来源', '报告日期', '最终产出', '下一步', '操作')):
            col.markdown(f'<div class="assistant-history-head">{title}</div>', unsafe_allow_html=True)
    for goal in goals:
        with st.container(key=f'completed-row-{goal.id}'):
            columns = st.columns(widths, vertical_alignment='center')
            for col, value in zip(columns, completed_values(goal, app._member_display(people.get(goal.member_id)))):
                value = escape(str(value), quote=True)
                col.markdown(f'<div class="assistant-history-cell" title="{value}">{value}</div>', unsafe_allow_html=True)
            columns[-1].button('查看', key=f'completed-view-{goal.id}', on_click=open_care, args=(app, goal))


def _cards(app, people, goals):
    from executive_health_ai.ui.pages.manager import care_activity
    for index, goal in enumerate(goals):
        if index % 3 == 0:
            columns = st.columns(min(3, len(goals) - index))
        if getattr(goal,'goal_type',None) == 'PROFILE_INTAKE':
            from executive_health_ai.ui.pages.manager.profile_intake import STATUS, progress_steps
            with columns[index % 3], st.container(border=True):
                st.markdown('**'+app._member_display(people.get(goal.member_id))+' · 健康资料导入**')
                st.write('当前：'+STATUS.get(goal.status,'待处理'))
                st.caption('开始：'+ux.when(goal.started_at))
                completed = [label for label,done,_ in progress_steps(goal) if done]
                st.caption('已完成：'+('、'.join(completed[-3:]) if completed else '尚无已完成步骤'))
                st.write('下一步：'+goal.next_action)
                st.button('处理资料与初评',key='profile-assistant-'+str(goal.id),on_click=open_care,args=(app,goal))
            continue
        activity = care_activity.load(goal)
        with columns[index % 3], st.container(border=True, key=f'assistant-card-{goal.id}'):
            st.markdown('**'+app._member_display(people.get(goal.member_id))+' · 体检后健康管理**')
            report = (goal.context_json or {}).get('report') or {}
            context, completed = st.columns([1.2, 1], gap='large')
            with context:
                st.caption('来源：' + (report.get('title') or '新体检报告'))
                if report.get('at'):
                    st.caption('报告日期：' + str(report['at'])[:10])
                if goal.status == 'COMPLETED' and goal.completed_at:
                    st.caption('完成时间：' + ux.local_time(goal.completed_at).strftime('%Y-%m-%d %H:%M'))
                st.markdown('**当前：'+activity.current+'**')
            with completed:
                st.caption('已完成')
                if activity.done:
                    for work in activity.done[-3:]:
                        st.write(work.mark+' '+work.title)
                else:
                    st.caption('工作已启动，完成记录将随实际处理更新。')
            st.divider()
            st.write('下一步：'+activity.next_action)
            if goal.status in {'WAITING_MANAGER','WAITING_INPUT','ESCALATED','FAILED'}:
                st.button('查看运行看板', key=f'assistant-open-{goal.id}', type='primary' if index==0 else 'secondary', on_click=open_care, args=(app,goal))
            else:
                st.caption('无需您操作')
                st.button('查看运行看板',key=f'assistant-progress-{goal.id}',on_click=open_care,args=(app,goal))


def progress(item):
    if item.source_type in {'post_checkup','profile_intake'}:
        return item.reason
    if item.status == '等待医生':
        return '已提交医学问题与依据'
    return {'task':'已明确执行安排','recheck':'已建立复查计划','service_request':'已接收服务安排',
        'risk_event':'已按现有规则核对数据','report_review':'已接收体检资料','consultation':'已建立会诊安排',
        'stage_review':'已汇集本阶段记录','intake_review':'已收到会员评估资料',
        'management_signal':'已汇集近期健康数据','automation_approval':'已准备后续安排'}.get(item.source_type, '已记录待处理事项')
