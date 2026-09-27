"""Health record upload and the shared assistant board, in business language."""
from html import escape
from pathlib import Path
from uuid import UUID
import pandas as pd
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, Document, Patient, AgentRunTrace, AgentPlanStep, DoctorReview, ReportExtractionRun
from executive_health_ai.agent import profile_intake as flow
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent.care_routing import latest
from executive_health_ai.services.profile_ingestion import ProfileIngestionService, TYPES, candidates, confirmed_profile, business_evidence, FIELD_LABELS
from executive_health_ai.services.responsibility import LABELS as RESPONSIBILITY
from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.presentation import data_table

STATUS={'RUNNING':'正在整理健康资料','PROCESSING':'正在整理健康资料','WAITING_MANAGER':'等待健管确认',
    'WAITING_DOCTOR':'等待医生判断','ESCALATED':'需要人工处理','COMPLETED':'已完成','WRITING':'正在写入档案'}


def open_board(app,goal):
    from executive_health_ai.ui.pages.manager.assistant import open_care
    open_care(app,goal,'会员360')


def entry(app,patient,view):
    key=f'profile-upload-{patient.id}'
    if st.button('＋ 导入健康资料',key=key+'-open',type='primary'):
        st.session_state[key]=True
    if st.session_state.get(key):
        with st.container(border=True):
            st.subheader('导入健康资料')
            st.caption(app._member_display(patient)+' · 上传后自动整理；确认前不会成为正式健康事实。')
            dtype=st.radio('请选择资料类型',list(TYPES),format_func=TYPES.get,horizontal=True,key=key+'-type')
            st.caption('支持含文字的 PDF、图片、Word、表格、文本和原生问卷文件。无法可靠读取时会保留原文件并提示人工处理。')
            file=st.file_uploader('上传资料',type=['pdf','png','jpg','jpeg','docx','xlsx','csv','txt','json'],key=key+'-file')
            if st.button('上传并整理资料',type='primary',disabled=file is None,key=key+'-submit'):
                try:
                    with SessionLocal() as session:
                        goal,duplicate=ProfileIngestionService().upload(session,patient.id,file.name,file.getvalue(),dtype,actor=view.owner,role='HEALTH_MANAGER')
                        session.commit()
                    st.session_state[key]=False
                    open_board(app,goal);st.rerun()
                except (ValueError,PermissionError) as exc:st.error(str(exc))
            if st.button('取消上传',key=key+'-cancel'):
                st.session_state[key]=False;st.rerun()


def history(app,patient):
    with SessionLocal() as session:
        goals=list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==patient.id,AgentGoal.goal_type=='PROFILE_INTAKE').order_by(AgentGoal.started_at.desc())))
        rows=[]
        for goal in goals:
            doc=session.get(Document,UUID(goal.source_id));run=session.get(ReportExtractionRun,UUID(goal.context_json['run_id']))
            rows.append({'时间':ux.when(goal.started_at),'资料类型':TYPES[goal.context_json['document_type']],
                '文件':doc.title,'解析状态':'已整理' if run.status=='COMPLETED' else STATUS.get(goal.status,'待处理'),
                '识别数量':run.candidate_count,'确认状态':STATUS.get(goal.status,'待处理'),'上传人':goal.created_by})
    st.subheader('资料导入记录')
    chosen=data_table(goals,rows,key=f'profile-history-{patient.id}',auto_select=False,activate_on_cell=True,empty='上传的资料及处理进度会保留在这里。')
    if chosen:open_board(app,chosen);st.rerun()


def confirmed_records(patient_id):
    with SessionLocal() as session: rows=confirmed_profile(session,patient_id)
    if rows:
        st.subheader('已确认健康资料')
        st.caption('保留资料原始来源。历史病史与自述用药不代表新诊断或新的用药方案。')
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')


def doctor_context(review):
    with SessionLocal() as session:
        goal=next((g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id==review.patient_id,
            AgentGoal.goal_type=='PROFILE_INTAKE')) if g.context_json.get('review_id')==str(review.id)),None)
        if not goal:return
        doc=session.get(Document,UUID(goal.source_id))
        rows=candidates(session,goal)
    st.caption('系统已整理本次上传资料。以下为原文待核实内容，不是系统医学结论。')
    st.dataframe(pd.DataFrame([{'项目':FIELD_LABELS.get(r.raw_name,r.raw_name) or '原文结论','本次资料':r.summary or r.raw_value,
        '单位':r.unit or '—','资料日期':r.structured_data_json.get('source_date') or '待确认',
        '原文依据':business_evidence(r)} for r in rows]),hide_index=True,width='stretch')
    path=Path(doc.storage_reference)
    if path.is_file():st.download_button('查看本次原始资料',path.read_bytes(),file_name=doc.title,key='profile-doctor-file-'+str(review.id))
    return True


def detail(app,goal_id):
    with SessionLocal() as session:goal=session.get(AgentGoal,UUID(str(goal_id)))
    if not flow.is_profile_goal(goal):st.error('未找到本次资料导入。');return
    if st.button('← 返回健康档案'):
        st.session_state.pop('care-detail',None)
        app.request_navigation(surface='运营后台',ops_page='成员',member_id=goal.member_id,member_section='健康',rerun=False)
        st.session_state.pop(f'archive-content-{goal.member_id}',None);st.rerun()
    @st.fragment(run_every=2 if goal.status in {'RUNNING','PROCESSING'} else 15 if goal.status=='WAITING_DOCTOR' else None)
    def live():
        with SessionLocal() as session:
            current=session.get(AgentGoal,goal.id)
            render(app,session,current)
        if current.status=='RUNNING':
            with SessionLocal() as session:
                HealthOpsAgentSupervisor().execute_next_step(session,goal.id)
                session.commit()
        if current.status!=goal.status:st.rerun()
    live()


def render(app,session,goal):
    doc=session.get(Document,UUID(goal.source_id));patient=session.get(Patient,goal.member_id)
    rows=candidates(session,goal);route=latest(session,goal)
    traces=list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id,
        AgentRunTrace.action.in_(('profile_activity','profile_exception'))).order_by(AgentRunTrace.started_at)))
    steps=list(session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id).order_by(AgentPlanStep.step_order)))
    with st.container(border=True):
        st.header('健康管理助手 · 健康资料导入')
        st.subheader(app._member_display(patient))
        st.caption('开始原因：收到'+TYPES[goal.context_json['document_type']]+' · '+doc.title+' · '+ux.when(goal.started_at))
        c.summary_strip([('当前',STATUS.get(goal.status,'待处理')),('当前责任',RESPONSIBILITY[route.route_type] if route else '系统自动处理'),('责任健管',goal.owner)])
        st.divider()
        cols=st.columns(6)
        for col,step in zip(cols,steps):
            col.markdown(('✓ ' if step.status=='COMPLETED' else '● ' if step.step_type==goal.current_stage else '○ ')+flow.LABELS[step.step_type])
    if goal.status=='COMPLETED':
        st.success('本次健康资料已整理完成')
        out=goal.context_json['output']
        c.summary_strip([('体检报告',out['reports']),('新增健康测量',out['measurements']),('更新健康档案',out['profile']),('新增历史记录',out['history']),('需要后续处理',out['deferred'])])
        st.write('会员360：已同步 · 成员端：已同步（同一份正式健康档案）')
        st.info('下一步：'+goal.next_action+' · 负责人：'+goal.owner)
        if st.button('返回会员360',type='primary'):
            st.session_state.pop('care-detail',None);app._open_member(goal.member_id);st.rerun()
    else:
        with st.container(border=True):
            st.subheader('现在需要您处理' if goal.status=='WAITING_MANAGER' else '当前正在处理')
            st.write(goal.next_action)
            st.caption('输入：本次资料、已有健康档案与测量记录。核对新增、一致、时间变化及冲突；年度基线保持原有确认语义。')
            if route:st.caption('为什么：'+route.reason_summary)
    if goal.context_json.get('review_id'):
        review=session.get(DoctorReview,UUID(goal.context_json['review_id']))
        with st.container(border=True):
            st.subheader('医生判断')
            st.write(review.question_for_doctor)
            st.write(review.opinion if review.status=='CONFIRMED' else '等待医生提交 · 当前无需重复整理资料')
    if goal.status=='ESCALATED':
        st.warning(goal.next_action)
        if st.button('重新尝试整理'):
            try:
                flow.retry(session,goal,actor=goal.owner,role='HEALTH_MANAGER');session.commit();st.rerun()
            except ValueError as exc:st.error(str(exc))
        if st.button('人工补充初始评估'):
            st.session_state.pop('care-detail',None)
            st.session_state[f'archive-content-{goal.member_id}']='初始评估'
            app.request_navigation(surface='运营后台',ops_page='成员',member_id=goal.member_id,member_section='健康',rerun=False);st.rerun()
    if rows:
        st.subheader('资料已整理，请确认档案更新' if goal.status=='WAITING_MANAGER' else '本次识别资料')
        comparison=goal.context_json.get('comparison',{})
        table=[]
        for row in rows:
            state,old,suggestion=comparison.get(str(row.id),('待核对','','正在核对档案'))
            table.append({'字段':(row.source_section+' · '+FIELD_LABELS.get(row.raw_name,row.raw_name)) if row.candidate_type=='PROFILE_FACT' else row.raw_name or '报告结论','现有内容':old or '暂无',
                '本次资料':row.summary or ' '.join(str(v or '') for v in (row.normalized_value or row.raw_value,row.unit)),
                '来源':row.structured_data_json.get('source_type','本次资料')+' · '+(row.structured_data_json.get('source_date') or '日期待确认'),
                '系统建议':suggestion,'状态':state,'处理':'暂不确认' if state in {'冲突','无法确认'} else '采用新资料'})
        c.summary_strip([('本次识别',len(rows)),('可新增',sum(r['状态']=='新增' for r in table)),
            ('新增时间点',sum(r['状态']=='更新' for r in table)),('存在冲突',sum(r['状态']=='冲突' for r in table)),('无法确认',sum(r['状态']=='无法确认' for r in table))])
        if goal.status=='WAITING_MANAGER':
            st.caption('冲突默认暂不确认。选择采用新资料、保留当前记录或暂不确认；未确认内容不会显示为成员正式档案。')
            with st.form('profile-approval-'+str(goal.id)):
                edited=st.data_editor(pd.DataFrame(table),hide_index=True,width='stretch',disabled=[k for k in table[0] if k!='处理'],
                    height=min(355,38+35*len(table)), column_config={'处理':st.column_config.SelectboxColumn('处理',options=['采用新资料','保留当前记录','暂不确认'],required=True)},key='profile-decisions-'+str(goal.id))
                submitted=st.form_submit_button('确认并更新健康档案',type='primary')
            if submitted:
                try:
                    flow.confirm(HealthOpsAgentSupervisor(),session,goal,{str(r.id):edited.iloc[i]['处理'] for i,r in enumerate(rows)},actor=goal.owner,role='HEALTH_MANAGER')
                    session.commit();st.rerun()
                except (ValueError,PermissionError) as exc:session.rollback();st.error(str(exc))
            with st.expander('需要医学判断时提交医生'):
                question=st.text_area('需要医生判断的问题')
                if st.button('提交医生判断'):
                    try:
                        flow.request_doctor(session,goal,question=question,actor=goal.owner,role='HEALTH_MANAGER');session.commit();st.rerun()
                    except (ValueError,PermissionError) as exc:st.error(str(exc))
        else:st.dataframe(pd.DataFrame(table).drop(columns='处理'),hide_index=True,width='stretch')
        with st.expander('查看提取依据'):
            st.dataframe(pd.DataFrame([{'项目':FIELD_LABELS.get(r.raw_name,r.raw_name) or '原文结论','原文依据':business_evidence(r),
                '资料日期':r.structured_data_json.get('source_date') or '未注明','页码':r.source_page} for r in rows]),hide_index=True,width='stretch')

    left,right=st.columns([1.15,1])
    with left,st.container(border=True):
        st.subheader('助手工作记录')
        for item in traces:
            marker='! ' if item.status=='FAILED' or item.action=='profile_exception' else '✓ '
            st.write(marker+ux.when(item.started_at)+' · '+item.result_summary)
    with right,st.container(border=True):
        st.subheader('接下来')
        st.write('请先核对原文件，重新上传可读取版本或人工补充；处理完成后再继续档案确认。' if goal.status=='ESCALATED' else
            '医生提交后自动继续，健管确认最终档案更新。' if goal.status=='WAITING_DOCTOR' else
            '确认来源与冲突 → 写入健康档案 → 更新现有健康趋势 → 同步会员360和成员端')
        st.caption('自述、原文医学结论和客观测量分开保留；系统不推断诊断、开药或决定风险。')
        path=Path(doc.storage_reference)
        if path.is_file():st.download_button('查看原文件',path.read_bytes(),file_name=doc.title,key='profile-source-'+str(goal.id))
