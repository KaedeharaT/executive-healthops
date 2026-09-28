"""One result input and one confirmation CTA in the existing active item."""
from datetime import datetime, time
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.services import care_results
from executive_health_ai.ui.pages.manager.care_runtime import panel
from executive_health_ai.ui import experience as ux


def render(patient,view,item,request_key):
    with SessionLocal() as session:
        goal=next((g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id==patient.id,
            AgentGoal.goal_type=='FOLLOWUP_RESULT',AgentGoal.status.not_in(('COMPLETED','CANCELLED')))
            .order_by(AgentGoal.started_at.desc())) if g.context_json.get('task_id')==str(item.record.id)),None)
        proposals=care_results.proposals(session,goal) if goal and goal.status=='WAITING_MANAGER' else []
    if goal:
        panel(goal)
        if goal.status in {'RUNNING','PROCESSING'}:
            st.caption('原始记录已保存，健康管理助手正在整理。现在不需要重复填写。')
            return
        if goal.status!='WAITING_MANAGER':
            st.warning('本次整理尚未完成，原始记录已保留。请核对当前处理状态。')
            return
        st.subheader('本次处理结果')
        st.write(goal.context_json['text'])
        parsed=goal.context_json.get('parsed',{})
        if parsed.get('warning'):st.warning(parsed['warning'])
        st.markdown('**准备更新：管理日志与当前事项结果**')
        rows=[{'准备更新':'生活方式候选 · '+r['field'],'内容':r['value'],'依据':r['source_excerpt']}
            for r in parsed.get('facts',[])]
        rows += [{'准备更新':a['operation'],'内容':a['title']+' · '+a['date'],'依据':a['source_excerpt']} for a in proposals]
        if rows:st.dataframe(rows,hide_index=True,width='stretch')
        st.caption('生活方式记录保留原文来源；正式医疗事实继续通过原有核对流程。没有医疗依据的复查意向只建立协调事项。')
        with st.form('care-result-confirm-'+str(goal.id)):
            follow=st.date_input('下一次跟进日期',value=None) if goal.context_json['outcome']!='已完成' else None
            accepted=st.checkbox('我已核对本次结果与后续安排')
            save=st.form_submit_button('确认并保存本次结果',type='primary')
        if save:
            try:
                if not accepted:raise ValueError('请先核对本次结果与安排。')
                with SessionLocal() as session:
                    care_results.confirm(session,session.get(AgentGoal,goal.id),HealthOpsAgentSupervisor(),actor=view.owner,
                        role='HEALTH_MANAGER',follow_at=datetime.combine(follow,time(9),ux.LOCAL) if follow else None)
                    session.commit()
                from executive_health_ai.ui.pages.manager.action_loop import focus
                st.session_state.pop('action-request-'+item.id,None)
                focus(patient,'DONE:'+goal.context_json['outcome'])
            except (ValueError,PermissionError) as exc:st.error(str(exc))
        return
    st.subheader('本次处理结果')
    with st.form('action-process-'+item.id):
        result=st.text_area('记录处理结果',height=110,
            placeholder='例如：会员最近睡眠约6–7小时，准备10月15日去医院复查血脂。')
        outcome=st.radio('结果状态',['已完成','部分完成','未完成'],horizontal=True)
        st.caption('填写一次，助手自动整理管理记录与后续安排；保存前由您核对。')
        submitted=st.form_submit_button('整理本次结果',type='primary')
    if submitted:
        try:
            with SessionLocal() as session:
                care_results.submit(session,member_id=patient.id,program_id=view.program.id,task_id=item.record.id,
                    text=result,actor=view.owner,outcome=outcome,request_key=request_key)
                session.commit()
            st.rerun()
        except (ValueError,PermissionError) as exc:st.error(str(exc))
