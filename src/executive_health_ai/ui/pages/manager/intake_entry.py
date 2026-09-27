"""Discoverable entry to the existing annual intake, without duplicating facts."""
from datetime import datetime

import streamlit as st
import pandas as pd

from executive_health_ai.database import SessionLocal
from executive_health_ai.services.management_workflow import ManagementWorkflowService, STEPS
from executive_health_ai.ui import components as c, experience as ux

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


def progress(row):
    responses = row.responses if row else {}
    return sum(s in responses and (s != '当前用药 / 营养补充' or '最近用药' in responses)
               for s in WIZARD_STEPS[:-1])


def open_intake(patient, view, *, read_only=False, step=None, assessment_id=None):
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


def card(patient, view):
    row = view.intake
    status = state(row)
    with st.container(border=True, key='neu-initial-assessment'):
        st.subheader('初始健康评估')
        c.summary_strip([('状态', status), ('已完成部分', f'{progress(row)} / 10'),
                         ('最近保存', ux.local_time(row.updated_at).strftime('%Y-%m-%d %H:%M') if row and row.responses else '尚未开始')])
        if status == '未开始':
            st.write('用于建立会员最初的健康资料和管理基础。')
            st.caption('基础资料 · 家族史 · 个人病史 · 手术/住院 · 过敏 · 用药 · 生活方式 · 环境暴露 · 本人希望改善的问题 · 专项症状评估')
        elif status == '待健管确认':
            st.write('会员资料已提交，请进行健管初评。')
        elif status == '待医生确认':
            st.write('涉及医学判断的资料已提交医生；医生确认后继续健管初评。')
        elif status == '已完成':
            completed = row.review.get('confirmed_at')
            completed = datetime.fromisoformat(completed) if completed else row.updated_at
            st.caption('完成时间：' + ux.local_time(completed).strftime('%Y-%m-%d %H:%M') + ' · 健管确认：已完成 · ' + (row.reviewed_by or view.owner))
            st.write('本人关注：' + (row.member_concern or '未填写'))
            st.write('专业管理重点：' + (row.professional_focus or '未填写'))
        label = {'未开始':'开始评估', '填写中':'继续填写', '待健管确认':'开始健管确认',
                 '待医生确认':'查看评估', '已完成':'查看评估'}[status]
        st.button(label, key=f'intake-entry-{patient.id}', type='primary', on_click=open_intake,
                  args=(patient, view), kwargs={'read_only':status in {'已完成','待医生确认'}})
        if row and (row.review or {}).get('import_prefill'):
            st.caption(f"系统已根据已有资料预填 {len(row.review['import_prefill'])} 项；请核对来源并补充其余部分。")
        if status == '填写中':
            st.button('查看已填写内容', key=f'intake-preview-{patient.id}', on_click=open_intake,
                      args=(patient, view), kwargs={'read_only':True})
        if status == '已完成':
            st.button('补充/修正', key=f'intake-amend-{patient.id}',on_click=amend,args=(patient,view))
    st.divider()


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
