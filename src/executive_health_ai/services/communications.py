"""Preserve natural-language notes and require explicit professional attribution."""
import re
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from executive_health_ai.models import DoctorReview, HealthProgram
from executive_health_ai.models.goal_data import CommunicationRecord
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.management_workflow import owned, ManagementWorkflowService


def record(session,*,member_id,program_id,raw_note,actor,role,channel='沟通',request_key,
           source='MANAGER',doctor_review_id=None,occurred_at=None):
    if role not in {'HEALTH_MANAGER','ADMIN','DOCTOR'}:raise PermissionError('请使用授权身份记录沟通。')
    if not raw_note.strip():raise ValueError('请记录本次沟通内容。')
    program=owned(session,HealthProgram,program_id,member_id)
    prior=session.scalar(select(CommunicationRecord).where(CommunicationRecord.request_key==request_key))
    if prior:
        if prior.patient_id!=member_id or prior.raw_note!=raw_note:raise ValueError('记录请求已用于其它内容。')
        return prior
    doctor=None
    if doctor_review_id:
        doctor=owned(session,DoctorReview,doctor_review_id,member_id)
        if doctor.status!='CONFIRMED':raise ValueError('医生意见尚未确认。')
    if source=='DOCTOR' and role!='DOCTOR' and not doctor:
        raise PermissionError('健管转述必须关联已确认医生意见，不能自行声明医生来源。')
    medical=source=='DOCTOR' and (role=='DOCTOR' or doctor is not None)
    at=occurred_at or utc_now()
    if at.tzinfo is None:raise ValueError('沟通时间必须包含时区。')
    weeks=re.search(r'([一二两三四五六七八九十\d]+)\s*周',raw_note)
    numerals={'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    days=7*(int(weeks[1]) if weeks and weeks[1].isdigit() else numerals.get(weeks[1],0) if weeks else 0)
    due=at+timedelta(days=days) if 0<days<=365 else None
    metrics=[code for word,codes in [('血压',['systolic_bp','diastolic_bp']),('睡眠',['sleep_duration']),
        ('体重',['weight']),('血糖',['glucose']),('活动',['steps'])] if word in raw_note for code in codes]
    attributed_name=doctor.doctor_name if doctor else actor
    opinion=(doctor.opinion if doctor else raw_note) if medical else None
    clinical_due=None
    if opinion and not re.search(r'(?:不|无需|不要|暂不|不必|未建议).{0,4}复查',opinion):
        clinical_weeks=re.search(r'([一二两三四五六七八九十\d]+)\s*周',opinion)
        clinical_days=7*(int(clinical_weeks[1]) if clinical_weeks and clinical_weeks[1].isdigit()
            else numerals.get(clinical_weeks[1],0) if clinical_weeks else 0)
        if '复查' in opinion and 0<clinical_days<=365:clinical_due=at+timedelta(days=clinical_days)
    summary={'record_type':'医生协同' if medical else '管理沟通','summary':raw_note,
        'doctor_opinion':opinion,'doctor_name':attributed_name if medical else None,
        'medical_statement_status':'已确认医生来源' if medical else '转述或管理记录，非正式医生意见',
        'monitoring':'家庭血压监测' if '血压' in raw_note and '监测' in raw_note else None,
        'followup_at':due.isoformat() if due else None,
        'recheck_requested':bool('复查' in raw_note and due),
        'clinical_recheck_at':clinical_due.isoformat() if clinical_due else None,'responsibility':'健管跟进'}
    from executive_health_ai.services.management_goals import current
    goal=current(session,program.id)
    row=CommunicationRecord(patient_id=member_id,program_id=program.id,occurred_at=at,participants=[actor],
        participant_roles={actor:role,**({doctor.doctor_name:'DOCTOR'} if doctor else {})},channel=channel,
        raw_note=raw_note,structured_summary=summary,source=source,related_goal_id=goal.id if goal else None,
        related_metrics=metrics,doctor_review_id=doctor.id if doctor else None,
        evidence=str(doctor.id) if doctor else '人工沟通原文',request_key=request_key)
    session.add(row);session.flush()
    return row


def confirm(session,row,*,actor,role):
    if role not in {'HEALTH_MANAGER','ADMIN'}:raise PermissionError('后续管理安排需要健管确认。')
    if row.confirmed_status=='CONFIRMED':return row
    from datetime import datetime
    summary=row.structured_summary;service=ManagementWorkflowService()
    due=datetime.fromisoformat(summary['followup_at']) if summary.get('followup_at') else None
    next_action=summary.get('monitoring') or ('核对下次复查安排' if summary.get('recheck_requested') else '')
    log=service.record_log(session,row.patient_id,row.program_id,actor=actor,request_key='communication:'+str(row.id),
        category='会诊' if row.source=='DOCTOR' else '日常跟进',channel=row.channel,occurred_at=row.occurred_at,
        member_issue=row.raw_note,manager_action='核对沟通来源并记录后续安排',result=summary['summary'],
        next_action=next_action,owner=actor,evidence=row.evidence,follow_up_at=due,
        related_doctor_review_id=row.doctor_review_id,create_followup=bool(due and next_action))
    actions=[{'kind':'log','id':str(log.id)}]
    if log.follow_up_task_id:actions.append({'kind':'followup','id':str(log.follow_up_task_id)})
    # A manager's own statement never becomes an order. A formal recheck needs
    # an already confirmed professional source, not the presence of '医生' in text.
    if summary.get('clinical_recheck_at') and row.doctor_review_id:
        review=session.get(DoctorReview,row.doctor_review_id)
        if review and '复查' in review.opinion:
            recheck=service.create_recheck(session,row.patient_id,row.program_id,title='按医生意见复查',
                reason=review.opinion,planned_at=datetime.fromisoformat(summary['clinical_recheck_at']),owner=actor,doctor_review_id=review.id,evidence=row.evidence)
            actions.append({'kind':'recheck','id':str(recheck.id)})
    row.related_actions=actions;row.log_id=log.id;row.confirmed_status='CONFIRMED';row.confirmed_by=actor
    session.flush()
    return row
