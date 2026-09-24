"""Business progress from the existing goals; no second queue or state store."""
from datetime import datetime, timedelta
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal
from executive_health_ai.agent.post_checkup import is_care_goal
from executive_health_ai.ui import components as c, experience as ux


def open_care(app, goal, origin='今日工作'):
    st.session_state['care-detail'] = str(goal.id)
    st.session_state['care-origin'] = origin
    app.request_navigation(surface='运营后台', ops_page='今日', rerun=False)


def assistant(app, people):
    with SessionLocal() as session:
        goals = [g for g in session.scalars(select(AgentGoal).order_by(AgentGoal.updated_at.desc())) if is_care_goal(g)]
    active = [g for g in goals if g.status not in {'COMPLETED', 'CANCELLED'}]
    recent = [g for g in goals if g.status == 'COMPLETED' and ux.local_time(g.updated_at) >= datetime.now(ux.LOCAL)-timedelta(days=7)]
    st.subheader('健康管理助手')
    c.summary_strip([('正在自动处理', sum(g.status == 'RUNNING' for g in active)),
        ('等待我确认', sum(g.status in {'WAITING_MANAGER','WAITING_INPUT','ESCALATED','FAILED'} for g in active)),
        ('等待医生', sum(g.status == 'WAITING_DOCTOR' for g in active)), ('最近完成', len(recent))])
    if not active:
        st.caption('当前没有需要您处理的自动流程。')
        return
    priorities = {'WAITING_MANAGER':0,'WAITING_INPUT':1,'ESCALATED':1,'FAILED':1,'WAITING_DOCTOR':2,'RUNNING':3}
    for goal in sorted(active, key=lambda g: priorities.get(g.status, 4))[:3]:
        member, state, action = st.columns([2, 1.5, 1])
        member.markdown('**'+app._member_display(people.get(goal.member_id))+' · 体检后健康管理**')
        labels = {'WAITING_MANAGER':'等待您的确认','WAITING_DOCTOR':'正在等待医生判断','RUNNING':'正在自动整理',
                  'WAITING_INPUT':'需要补充资料','ESCALATED':'需要人工核对','FAILED':'需要人工协助'}
        state.write(labels.get(goal.status, '处理中'))
        if goal.status in {'WAITING_MANAGER','WAITING_INPUT','ESCALATED','FAILED'}:
            action.button('继续处理', key=f'assistant-open-{goal.id}', on_click=open_care, args=(app,goal))
        else:
            action.caption('无需您操作')


def progress(item):
    if item.source_type == 'post_checkup':
        return item.reason
    if item.status == '等待医生':
        return '已提交医学问题与依据'
    return {'task':'已明确执行安排','recheck':'已建立复查计划','service_request':'已接收服务安排',
        'risk_event':'已按现有规则核对数据','report_review':'已接收体检资料','consultation':'已建立会诊安排',
        'stage_review':'已汇集本阶段记录','intake_review':'已收到会员评估资料',
        'management_signal':'已汇集近期健康数据','automation_approval':'已准备后续安排'}.get(item.source_type, '已记录待处理事项')
