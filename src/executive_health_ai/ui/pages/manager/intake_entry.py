"""Discoverable entry to the existing annual intake, without duplicating facts."""
from datetime import datetime

import streamlit as st
import pandas as pd

from executive_health_ai.database import SessionLocal
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS

WIZARD_STEPS = tuple(s for s in STEPS if s != '最近用药')


def state(row):
    if row is None or row.status == 'DRAFT' and not row.responses:
        return '未开始'
    if row.status == 'DRAFT':
        return '填写中'
    if row.review_status == 'WAITING_MEDICAL_REVIEW':
        return '待医生确认'
    if row.status == 'CONFIRMED' and row.review_status == 'CONFIRMED':
        return '已完成'
    return '待健管确认'


def open_intake(patient, view, *, read_only=False, step=None, assessment_id=None):
    for key in list(st.session_state):
        if key.startswith(f'intake-select-{patient.id}-'):
            st.session_state.pop(key,None)
    if assessment_id:st.session_state[f'intake-assessment-id-{patient.id}']=str(assessment_id)
    else:st.session_state.pop(f'intake-assessment-id-{patient.id}',None)
    if not view.intake and not assessment_id:
        with SessionLocal() as session:
            ManagementWorkflowService().start_intake(session, patient.id,
                (view.program.cycle_year or view.program.start_date.year) if view.program else datetime.now().year,
                view.owner)
            session.commit()
    st.session_state[f'archive-content-{patient.id}'] = '初始评估'
    st.session_state[f'intake-readonly-{patient.id}'] = read_only
    if step in WIZARD_STEPS:
        st.session_state[f'intake-step-{patient.id}'] = WIZARD_STEPS.index(step)
    else:
        st.session_state.pop(f'intake-step-{patient.id}', None)


def return_to_archive(app, patient):
    st.session_state.pop(f'intake-assessment-id-{patient.id}', None)
    st.session_state.pop(f'archive-content-{patient.id}', None)
    st.session_state.pop(f'intake-readonly-{patient.id}', None)
    st.session_state[f'archive-content-{patient.id}-epoch'] = st.session_state.get(f'archive-content-{patient.id}-epoch', 0) + 1
    if app:
        app.request_navigation(surface='运营后台', ops_page='成员', member_id=patient.id, member_section='健康', rerun=False)


def amend(patient, view, step=None):
    row = view.intake
    if row and row.status == 'CONFIRMED':
        with SessionLocal() as session:
            ManagementWorkflowService().review_intake(session, patient.id, row.id, focus=row.professional_focus,
                missing='', tests=row.review.get('supplementary_tests',''),
                medical_question=row.review.get('medical_question',''), annual_focus=row.review.get('annual_focus',''),
                actor=view.owner, decision='RETURN')
            session.commit()
    open_intake(patient, view, step=step)


def answers(row):
    """Display the same answers, clearly distinguished from medical facts."""
    st.caption('以下为会员自述资料；健管核对不等于正式医学诊断或用药确认。')
    for label, data in row.responses.items():
        st.markdown('**' + label + '**')
        if label == '基础资料':
            st.caption('使用会员现有基础档案；身高、体重沿用健康数据入口。')
        elif isinstance(data, list):
            if data:
                st.dataframe(pd.DataFrame(data),hide_index=True,width='stretch',key=f'intake-summary-{row.id}-{label}')
            else:
                st.caption('本次未提供已知记录，仍需核对。')
        elif isinstance(data, dict):
            st.dataframe(pd.DataFrame([{'项目':k, '回答':v or '待补充'} for k,v in data.items()]),
                         hide_index=True,width='stretch',key=f'intake-summary-{row.id}-{label}')
