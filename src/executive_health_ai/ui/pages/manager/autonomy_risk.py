"""Compact governed RED handoff; emergency routing keeps its existing renderer."""
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, DoctorReview, RiskEvent, Task
from executive_health_ai.ui import experience as ux


def render(patient, event):
    with SessionLocal() as session:
        goal=next((g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id==patient.id,
            AgentGoal.goal_type=='DAILY_CARE')) if g.context_json.get('risk_event_id')==str(event.id)),None)
        if not goal:return False
        role=goal.context_json.get('responsibility',{}).get('route_type')
        if role not in {'MANAGER','DOCTOR'}:return False
        review=session.scalar(select(DoctorReview).where(DoctorReview.risk_event_id==event.id).order_by(DoctorReview.created_at.desc()))
        tasks=list(session.scalars(select(Task).where(Task.risk_event_id==event.id,Task.status.not_in(('COMPLETED','CANCELLED')))))
    st.subheader('优先处理')
    st.caption(':red[需要人工 / 医学判断]')
    st.write(ux.business_text(event.summary))
    st.caption('已核对资料、当前阶段和既有安排；正式风险不会因摘要内容改变。')
    if review and review.status=='PENDING':
        st.info('等待医生判断 · 当前责任：'+(review.doctor_name if review.doctor_name!='待分配医生' else '内部医生'))
        st.write(review.question_for_doctor)
        return True
    if review:st.write('医生意见：'+review.opinion)
    if tasks:
        task=tasks[0]
        st.write('下一步：'+task.instruction)
        with st.form('autonomy-followup-'+str(event.id)):
            result=st.text_area('本次处理结果')
            if st.form_submit_button('确认',type='primary'):
                from executive_health_ai.services.task_transitions import TaskTransitionService
                try:
                    with SessionLocal() as session:
                        TaskTransitionService().complete(session,task.id,actor=goal.owner or '责任健管',outcome=result)
                        session.commit()
                    st.rerun()
                except ValueError as exc:st.error(str(exc))
    else:
        st.caption('当前责任：'+(goal.owner or '责任健管')+'。记录实际处理结果后才可关闭。')
        with st.form('autonomy-close-'+str(event.id)):
            reason=st.text_area('关闭原因')
            result=st.text_area('本次处理结果')
            if st.form_submit_button('确认',type='primary'):
                from executive_health_ai.services.risk_triage import RiskEvaluationService
                try:
                    with SessionLocal() as session:
                        RiskEvaluationService().close_manual_event(session,session.get(RiskEvent,event.id),
                            goal.owner or '责任健管',reason,result)
                        session.commit()
                    st.rerun()
                except ValueError as exc:st.error(str(exc))
    return True
