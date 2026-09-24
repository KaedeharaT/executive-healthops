"""Technical monitoring stays inside the administrator surface."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, AgentRunTrace, AgentPlanStep, Patient
from executive_health_ai.agent.post_checkup import is_care_goal, LABELS
from executive_health_ai.ui.presentation import data_table
from executive_health_ai.ui import experience as ux, components as c


def monitor():
    st.subheader('自动化运行')
    with SessionLocal() as session:
        goals = [g for g in session.scalars(select(AgentGoal).order_by(AgentGoal.started_at.desc())) if is_care_goal(g)]
        members = {p.id: p.display_name for p in session.scalars(select(Patient))}
    selected = data_table(goals, [{'会员': members.get(g.member_id, '会员'), '流程': '体检后健康管理',
        '入口事件': 'REPORT_UPLOADED', '当前状态': g.status, '当前业务步骤': LABELS.get(g.current_stage, g.current_stage),
        '等待对象': '医生' if g.status == 'WAITING_DOCTOR' else '健管' if g.status in {'WAITING_MANAGER','WAITING_INPUT'} else '—',
        '启动时间': ux.local_time(g.started_at), '最后更新时间': ux.local_time(g.updated_at),
        '异常': g.context_json.get('error', '')} for g in goals], key='care-admin-runs', search=True, auto_select=False)
    if selected:
        with c.detail_drawer('自动化运行详情',key='admin-care',table_key='care-admin-runs'):
            st.caption(f'Goal: {selected.id} · State: {selected.current_stage}')
            st.write(selected.title)
            with SessionLocal() as session:
                steps = list(session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id == selected.current_plan_id).order_by(AgentPlanStep.step_order)))
                traces = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id == selected.id).order_by(AgentRunTrace.started_at)))
            data_table(steps, [{'Step': x.step_type, 'State': x.status, 'Approval': x.approval_role or '—', 'Wait': x.wait_event_type or '—'} for x in steps], key='care-admin-steps', selectable=False)
            trace = data_table(traces, [{'时间': ux.local_time(t.started_at), 'Tool': t.tool_name or '—', 'Action': t.action,
                                       'State': t.status, 'Error': t.error_summary or '—'} for t in traces], key='care-admin-trace', auto_select=False)
            if trace:
                with st.expander('输入 / 结构化结果摘要', expanded=True):
                    st.text(trace.result_summary or trace.error_summary or '无额外内容')
            if selected.status in {'ESCALATED','FAILED','WAITING_INPUT'}:
                if st.button('重新读取已补充资料', key='care-admin-retry'):
                    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
                    with SessionLocal() as session:
                        HealthOpsAgentSupervisor().resume_goal(session, selected.id, actor='管理员')
                        session.commit()
                    st.rerun()
