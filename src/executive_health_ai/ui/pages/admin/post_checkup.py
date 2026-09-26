"""Technical monitoring stays inside the administrator surface."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, AgentRunTrace, AgentPlanStep, Patient
from executive_health_ai.agent.post_checkup import is_care_goal, LABELS
from executive_health_ai.ui.presentation import data_table
from executive_health_ai.ui import experience as ux, components as c


def monitor():
    if identity := st.session_state.get('admin-care-board'):
        from uuid import UUID
        from executive_health_ai.ui.pages.manager.operations_board import render
        with SessionLocal() as session:
            goal=session.get(AgentGoal,UUID(identity))
        if st.button('← 返回自动化运行'):
            st.session_state.pop('admin-care-board',None)
            st.session_state['admin-care-epoch']=st.session_state.get('admin-care-epoch',0)+1
            st.rerun()
        render(None,goal,admin=True)
        if goal.status in {'ESCALATED','FAILED','WAITING_INPUT'}:
            if st.button('重新读取已补充资料',key='care-admin-retry'):
                from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
                with SessionLocal() as session:
                    HealthOpsAgentSupervisor().resume_goal(session,goal.id,actor='管理员')
                    session.commit()
                st.rerun()
        return
    st.subheader('自动化运行')
    with SessionLocal() as session:
        goals = [g for g in session.scalars(select(AgentGoal).order_by(AgentGoal.started_at.desc())) if is_care_goal(g)]
        members = {p.id: p.display_name for p in session.scalars(select(Patient))}
    selected = data_table(goals, [{'会员': members.get(g.member_id, '会员'), '流程': '体检后健康管理',
        '入口事件': 'REPORT_UPLOADED', '当前状态': g.status, '当前业务步骤': LABELS.get(g.current_stage, g.current_stage),
        '等待对象': '医生' if g.status == 'WAITING_DOCTOR' else '健管' if g.status in {'WAITING_MANAGER','WAITING_INPUT'} else '—',
        '启动时间': ux.local_time(g.started_at), '最后更新时间': ux.local_time(g.updated_at),
        '异常': g.context_json.get('error', '')} for g in goals], key=f"care-admin-runs-{st.session_state.get('admin-care-epoch',0)}", search=True, auto_select=False)
    if selected:
        st.session_state['admin-care-board']=str(selected.id)
        st.rerun()
