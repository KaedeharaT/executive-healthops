"""Operational evidence inside the existing administrator surface."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import MemberAgent,Patient,AgentRunTrace,HealthEvent
from executive_health_ai.services.care_memory import working,longitudinal
from executive_health_ai.ui import experience as ux


def identities():
    with SessionLocal() as session:
        rows=session.execute(select(MemberAgent,Patient).join(Patient,Patient.id==MemberAgent.member_id)
            .where(Patient.archived_at.is_(None))).all()
    st.subheader('会员长期工作状态')
    st.dataframe([{'会员':p.display_name,'状态':a.status,'等待':a.waiting_for or '—',
        '下次唤醒':ux.local_time(a.next_wake_at),'累计事件唤醒':a.wake_count} for a,p in rows],hide_index=True,width='stretch')


def detail(goal):
    from executive_health_ai.ui.pages.manager.care_runtime import panel
    panel(goal)
    with SessionLocal() as session:
        traces=list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id).order_by(AgentRunTrace.started_at)))
        events=list(session.scalars(select(HealthEvent).where(HealthEvent.goal_id==goal.id).order_by(HealthEvent.received_at)))
        memory=working(session,goal);history=longitudinal(session,goal.member_id)
    st.subheader('持久化执行记录')
    st.dataframe([{'时间':ux.local_time(t.started_at),'动作':t.action,'工具':t.tool_name or '—','状态':t.status,
        '结果引用':str((t.metadata_json or {}).get('result_reference') or t.result_summary or '')[:400],
        '错误':t.error_summary or ''} for t in traces],hide_index=True,width='stretch')
    st.caption('只记录调用、结果来源与等待恢复，不记录或展示模型隐藏思维链。')
    with st.expander('事件与工作上下文'):
        st.dataframe([{'类型':e.event_type,'来源':e.source_type,'状态':e.status,'业务引用':e.source_id,
            '时间':ux.local_time(e.received_at)} for e in events],hide_index=True,width='stretch')
        st.write(memory)
        if history:st.dataframe(history,hide_index=True,width='stretch')
