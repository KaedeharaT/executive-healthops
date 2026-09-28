"""Shared medical records and details for the global and member views."""
from datetime import datetime
from uuid import UUID
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import DoctorReview, HealthAssessment, Alert, AgentGoal, AgentApprovalRequest, Encounter
from executive_health_ai.models.management_workflow import ConsultationCase
from executive_health_ai.services.product_projection import pending_doctor_work
from executive_health_ai.agent.post_checkup import goal_for_review, is_care_goal
from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.presentation import data_table


def medical_rows(session, member_id=None, history=False, doctor=False):
    if history:
        query = select(DoctorReview).where(DoctorReview.status=='CONFIRMED')
        if member_id: query=query.where(DoctorReview.patient_id==member_id)
        records=list(session.scalars(query))
    else:
        records=pending_doctor_work(session,member_id)
    rows=[]
    care={g.context_json.get('review_id'):g for g in session.scalars(select(AgentGoal)) if is_care_goal(g)}
    for r in records:
        kind='doctor_review' if isinstance(r,DoctorReview) else 'baseline_review' if isinstance(r,HealthAssessment) else 'legacy_medical_review'
        goal=care.get(str(r.id))
        changes='；'.join(f"{f['label']} {f['value']:g} {f['unit']}" for f in goal.context_json.get('findings',[])[:2]) if goal else '查看已提交资料'
        rows.append({'kind':kind,'record':r,'member_id':r.patient_id,'question':getattr(r,'question_for_doctor',None) or getattr(r,'title','年度基线医学确认'),
            'source':'体检后健康管理' if goal else '年度基线' if kind=='baseline_review' else '健康管理提交','change':changes,
            'doctor':getattr(r,'doctor_name','责任医生'),'at':getattr(r,'created_at',None),'state':'已完成' if history else '待判断'})
    pending_states=('PREPARING','SCHEDULED','WAITING_RESULT') if doctor else ('PREPARING','SCHEDULED','WAITING_RESULT','WAITING_ACTIONS')
    cases=select(ConsultationCase).where(ConsultationCase.status=='COMPLETED' if history else ConsultationCase.status.in_(pending_states))
    if member_id:cases=cases.where(ConsultationCase.patient_id==member_id)
    for r in session.scalars(cases):
        encounter=session.get(Encounter,r.encounter_id)
        rows.append({'kind':'consultation','record':r,'member_id':r.patient_id,'question':encounter.reason,'source':'正式会诊','change':'已整理会诊资料',
            'doctor':'、'.join(p['doctor'] for p in r.participants),'at':r.requested_at,
            'state':{'PREPARING':'资料准备','SCHEDULED':'待判断','WAITING_RESULT':'待汇总意见','WAITING_ACTIONS':'待健管执行','COMPLETED':'已完成'}[r.status]})
    if doctor and not history:
        approvals=session.execute(select(AgentApprovalRequest,AgentGoal).join(AgentGoal,AgentApprovalRequest.goal_id==AgentGoal.id).where(AgentApprovalRequest.required_role=='DOCTOR',AgentApprovalRequest.status=='PENDING'))
        for approval,goal in approvals:
            if member_id and goal.member_id!=member_id:continue
            rows.append({'kind':'approval','record':approval,'member_id':goal.member_id,'question':goal.next_action or goal.title,
                'source':'医学确认','change':'已有资料待确认','doctor':'责任医生','at':goal.started_at,'state':'待判断'})
    from executive_health_ai.services.member_archive import active_ids
    active=set(session.scalars(active_ids()))
    return [row for row in rows if row['member_id'] in active]


def review_detail(app, member, record_id, kind='doctor_review', doctor=False):
    from executive_health_ai.ui.pages.doctor.experience import detail
    from executive_health_ai.ui.pages.manager.post_checkup import doctor_detail
    if kind=='approval':
        from executive_health_ai.ui.pages.manager.experience import approvals
        approvals(app,member.id,'DOCTOR',selected_id=UUID(str(record_id)));return
    if kind=='consultation':
        from executive_health_ai.ui.pages.manager.workflow import consultations
        consultations(app,member,doctor=doctor,selected_id=UUID(str(record_id))); return
    with SessionLocal() as session:
        model={'doctor_review':DoctorReview,'baseline_review':HealthAssessment,'legacy_medical_review':Alert}[kind]
        record=session.get(model,UUID(str(record_id)))
        goal=goal_for_review(session,record.id,member.id) if kind=='doctor_review' else None
    if goal:
        doctor_detail(goal,read_only=not doctor)
    elif kind=='doctor_review':
        detail(app,member,record,read_only=not doctor)
    elif doctor:
        ctx=app._member_doctor_context(member.id)
        app._render_legacy_doctor_reviews(member,{**ctx,'reviews':[],'alerts':[record] if kind=='legacy_medical_review' else []})
    else:
        st.subheader('需要判断什么')
        st.write(getattr(record,'title','年度健康基线医学确认'))
        st.info('正在等待医生判断。提交后，后续工作会进入今日工作。')


def collaboration(app, patient=None):
    members=app._patient_map()
    key='medical-member-'+str(patient.id) if patient else 'medical-global'
    if st.session_state.get(key+'-detail'):
        kind,record_id,member_id=st.session_state[key+'-detail']
        if st.button('← 返回医疗记录',key=key+'-back'):
            st.session_state.pop(key+'-detail',None)
            st.session_state[key+'-epoch']=st.session_state.get(key+'-epoch',0)+1;st.rerun()
        review_detail(app,members[UUID(member_id)],record_id,kind)
        return
    if not patient:c.page_shell('manager','医疗协同','查看全部医学问题与交接进度；需要您处理的事情也会进入今日工作。')
    with SessionLocal() as session:
        pending=medical_rows(session,patient.id if patient else None,False)
        completed=medical_rows(session,patient.id if patient else None,True)
    if patient:
        scope=st.radio('医疗记录',['进行中','历史'],horizontal=True,key=key+'-scope')
        rows=completed if scope=='历史' else pending
    else:
        groups={'全部':pending+completed,'待提交医生':[r for r in pending if r['state']=='资料准备'],
            '等待医生':[r for r in pending if r['state']=='待判断'],
            '医生已返回':[r for r in pending if r['state']=='待汇总意见'],
            '待健管确认':[r for r in pending if r['state']=='待健管执行'],'完成':completed}
        scope=st.radio('医疗协同状态',list(groups),horizontal=True,format_func=lambda label:label+' '+str(len(groups[label])),key=key+'-stage')
        rows=groups[scope]
    selected=data_table(rows,[{'会员':app._member_display(members.get(r['member_id'])),'问题':r['question'],'类型':r['source'],
        '医生':r['doctor'],'状态':r['state'],'提交时间':ux.local_time(r['at']),
        '等待时间':f"{max(0,(datetime.now(ux.LOCAL)-ux.local_time(r['at'])).days)} 天" if r['at'] and r['state']!='已完成' else '—',
        '下一步':'确认行动拆解' if r['state']=='待健管执行' else '查看医生意见' if r['state']=='已完成' else '等待医学判断'} for r in rows],
        key=key,search=True,auto_select=False,activate_on_cell=True)
    if selected:
        st.session_state[key+'-detail']=(selected['kind'],str(selected['record'].id),str(selected['member_id']));st.rerun()
