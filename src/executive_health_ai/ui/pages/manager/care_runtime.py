"""Embed the shared progress panel beside the current business action."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal
from executive_health_ai.services.agent_progress import load
from executive_health_ai.ui.agent_progress import AgentProgressPanel, ai_timing


def panel(goal):
    running=goal.status in {'RUNNING','PROCESSING'}
    @st.fragment(run_every=4 if running else None)
    def display():
        with SessionLocal() as session:
            current=session.get(AgentGoal,goal.id)
            progress=load(session,current)
        if running and not progress.running:st.rerun()
        with st.container(key='agent-progress-'+str(goal.id)):
            AgentProgressPanel.render(progress,flow_name='健康管理助手 · '+current.title,next_action=current.next_action or '')
            ai_timing(progress)
    display()


def for_phase(member_id,phase_id):
    if not phase_id:return
    with SessionLocal() as session:
        goal=session.scalar(select(AgentGoal).where(AgentGoal.member_id==member_id,
            AgentGoal.goal_type=='STAGE_REVIEW',AgentGoal.source_id==str(phase_id),
            AgentGoal.status.not_in(('COMPLETED','CANCELLED'))))
    if goal:panel(goal)
