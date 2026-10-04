"""Compact evidence handoff shared by manager and doctor workspaces."""
from uuid import UUID
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, HealthEvent
from executive_health_ai.services.change_review import review_summary
from executive_health_ai.ui.experience import business_text


def render_for_risk(member_id, risk):
    if risk is None or risk.patient_id!=member_id:
        return
    with SessionLocal() as session:
        goal=session.scalar(select(AgentGoal).where(AgentGoal.member_id==member_id,
            AgentGoal.goal_type=='DAILY_CARE',
            AgentGoal.context_json['risk_event_id'].as_string()==str(risk.id))
            .order_by(AgentGoal.started_at.desc()).limit(1))
        if not goal or not goal.context_json.get('event_id'):
            return
        source=session.get(HealthEvent,UUID(goal.context_json['event_id']))
        if not source or source.member_id!=member_id or source.event_type!='MEANINGFUL_CHANGE':
            return
        evidence=review_summary(source.payload_ref,risk.risk_level,goal.context_json)
    st.write(evidence['message'])
    for checked in evidence['checked']:
        st.caption('✓ '+business_text(checked))
    st.write('当时核对后的处理：'+evidence['decision'])
