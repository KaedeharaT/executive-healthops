"""Executable Member360 workspace; every action stays with the selected member."""
from datetime import date,datetime,time,timedelta
from uuid import UUID,uuid4
import pandas as pd
import streamlit as st
from sqlalchemy import select
from executive_health_ai.database import SessionLocal
from executive_health_ai.models import DoctorReview,ServiceCatalogItem,HealthProgram
from executive_health_ai.services.management_action_loop import ManagementActionLoop
from executive_health_ai.ui import components as c,experience as ux
from executive_health_ai.ui.presentation import data_table
from executive_health_ai.ui.status_dictionary import status_label

service=ManagementActionLoop()
KINDS={'MANAGEMENT':'管理事项','FOLLOWUP':'随访','RECHECK':'复查','SERVICE':'服务','DOCTOR':'医生协同','RISK':'正式风险','STAGE_REVIEW':'阶段复盘'}

def open_next(app,patient):
    st.session_state[f'action-focus-{patient.id}']='NEXT'
    app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='管理')

def focus(patient,value):
    st.session_state[f'action-focus-{patient.id}']=value;st.rerun()

def clear(patient):
    st.session_state.pop(f'action-focus-{patient.id}',None);st.rerun()

def render(app,patient,view,*,show_recent=True,primary_next=True):
    from executive_health_ai.ui.pages.manager import workflow
    with SessionLocal() as session:state=service.project(session,patient.id,view.program.id if view.program else None)
    key=f'action-focus-{patient.id}';selected=st.session_state.get(key)
    if selected=='NEXT':
        selected=state['next'].id if state['next'] else state['state'];st.session_state[key]=selected
    if selected:
        if st.button('← 返回本会员管理工作区',key='action-back'):clear(patient)
        if selected.startswith('DONE:'):
            st.success('本次已完成' if selected=='DONE:已完成' else '管理记录已保存' if selected=='DONE:记录保存' else '本次处理已记录；原事项仍保持开放')
            if state['next']:
                st.write('下一步：'+state['next'].title)
                if st.button('继续处理下一项',type='primary'):focus(patient,state['next'].id)
            stage_prompt(patient,state,primary=not state['next'])
            following=st.session_state.get(f'action-following-{patient.id}')
            duplicate=set()
            if following in {'安排复查','申请服务','提交医生'}:
                label='提交医生判断' if following=='提交医生' else following
                if st.button('继续'+label,key='action-following'):focus(patient,'CREATE:'+label)
                duplicate.add(label)
            quick_actions(patient,exclude=duplicate)
            return True
        if selected=='CREATE':
            st.info('当前没有开放事项，可从下面直接开展管理工作。')
            quick_actions(patient);return True
        if selected in {'STAGE_REVIEW','NEXT_PHASE'}:
            stage_detail(patient,state);return True
        if selected.startswith('CREATE:'):
            create(app,patient,view,selected.split(':',1)[1]);return True
        item=next((i for i in state['items'] if i.id==selected),None)
        if not item:
            st.success('当前事项已结束或已更新。')
            if state['next']:
                st.write('下一步：'+state['next'].title)
                if st.button('继续处理下一项',type='primary'):focus(patient,state['next'].id)
            stage_prompt(patient,state,primary=not state['next']);quick_actions(patient);return True
        detail(app,patient,view,item);return True
    with st.container(border=True,key='soft-management-next'):
        st.subheader('当前阶段 · '+(state['phase'].title if state['phase'] else '待安排阶段'))
        st.caption(state['phase'].goal if state['phase'] else '可先记录工作、创建随访，或从年度方案与阶段建立计划。')
        st.subheader('下一件要做')
        if state['next']:
            item=state['next'];st.write(item.title)
            c.summary_strip([('负责人',item.owner),('截止时间',ux.when(item.due)),('来源',item.source),('状态',status_label(item.status))])
            if st.button('立即处理',type='primary' if primary_next else 'secondary',key='action-immediate'):focus(patient,item.id)
        else:st.write('当前阶段事项已处理，请确认阶段复盘或下一阶段。' if state['review'] or state['review_ready'] else '当前没有开放事项，可继续记录管理工作或安排后续。')
        stage_prompt(patient,state,primary=primary_next and not state['next'])
    quick_actions(patient)
    remaining=[i for i in state['items'] if not state['next'] or i.id!=state['next'].id]
    st.subheader('其他开放事项')
    item=data_table(remaining,[{'事项':i.title,'类型':KINDS[i.kind],'状态':status_label(i.status),'负责人':i.owner,'截止时间':ux.local_time(i.due),'来源':i.source,'下一步':i.next_action} for i in remaining],key=f'action-open-{patient.id}',auto_select=False,empty='没有其他开放事项；当前优先事项在上方处理。')
    if item:focus(patient,item.id)
    if show_recent:
        st.subheader('最近管理日志')
        workflow.log_rows(view.logs[:3],key=f'action-recent-{patient.id}')
    st.subheader('阶段进度')
    workflow.phases(view)
    return False

def quick_actions(patient,*,exclude=()):
    st.markdown('**快捷管理动作**')
    labels=[label for label in ['新增管理记录','创建随访','安排复查','申请服务','提交医生判断'] if label not in exclude]
    for col,label in zip(st.columns(len(labels)),labels):
        if col.button(label,key='action-create-'+label):focus(patient,'CREATE:'+label)

def stage_prompt(patient,state,*,primary=True):
    if state['review']:
        st.info('阶段复盘已经完成，下一阶段草稿待确认。')
        if st.button('进入下一阶段',type='primary' if primary else 'secondary',key='action-next-phase'):focus(patient,'NEXT_PHASE')
    elif state['review_ready']:
        st.success('本阶段主要事项已完成' if state['all_done'] else '本阶段可以复盘；请核对未执行、取消或仍待处理的事项。')
        st.write('本阶段可以复盘 · 已整理完成事项、管理日志、复查与服务结果；指标变化使用已有健康数据。')
        if st.button('开始阶段复盘',type='primary' if primary else 'secondary',key='action-review'):focus(patient,'STAGE_REVIEW')

def detail(app,patient,view,item):
    from executive_health_ai.ui.pages.manager import workflow
    with st.container(border=True,key='soft-management-detail'):
        st.subheader('当前事项详情')
        st.markdown('### '+item.title)
        c.summary_strip([('来源',item.source),('负责人',item.owner),('截止时间',ux.when(item.due)),('状态',status_label(item.status))])
        st.write('为什么需要处理：'+item.reason)
        st.write('相关数据 / 依据：'+(getattr(item.record,'evidence','') or getattr(item.record,'doctor_brief','') or item.reason))
        st.subheader('现在需要你做')
        if item.kind=='STAGE_REVIEW':
            with SessionLocal() as session:state=service.project(session,patient.id,view.program.id)
            stage_detail(patient,state);return
        if item.kind=='RECHECK':workflow.recheck_detail(patient,view,item.record);return
        if item.kind=='SERVICE':
            from executive_health_ai.ui.pages.manager.services import service_detail
            service_detail(app,item.record,patient);return
        if item.kind=='RISK':
            app._render_current_risk_actions(patient,selected_id=item.record.risk_event_id);return
        if item.kind=='DOCTOR':
            st.info('医学判断由医生完成。健管可以核对问题与资料，不能代替医生提交结论。')
            if isinstance(item.record,DoctorReview):
                from executive_health_ai.ui.pages.manager.medical import review_detail
                review_detail(app,patient,item.record.id)
            if st.button('进入本会员医生协同',type='primary'):
                app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='医疗')
            return
        if not view.program:
            st.info('此事项尚无当前管理计划。先建立有负责人和周期的计划，再保存处理结果。')
            create(app,patient,view,'创建随访');return
        request_key=st.session_state.setdefault('action-request-'+item.id,str(uuid4()))
        with st.form('action-process-'+item.id):
            fields,action=st.columns([3,1])
            with fields:
                result=st.text_area('随访情况 / 处理结果' if item.kind=='FOLLOWUP' else '处理结果',height=85)
                outcome=st.radio('结果状态',['已完成','部分完成','未完成'],horizontal=True)
                left,right=st.columns(2)
                following=left.selectbox('下一步',['无需后续','继续随访','安排复查','申请服务','提交医生'])
                follow=right.date_input('下一次跟进日期',value=None)
            with action:
                st.caption('核对处理结果后保存；完成后继续下一项。')
                submit=st.form_submit_button('完成本次处理',type='primary')
        if submit:
            try:
                with SessionLocal() as session:
                    service.process_task(session,patient.id,view.program.id,item.record.id,actor=view.owner,result=result,outcome=outcome,
                        next_action=following,follow_at=datetime.combine(follow,time(9),ux.LOCAL) if follow else None,request_key=request_key)
                    session.commit()
                st.session_state.pop('action-request-'+item.id,None)
                st.session_state[f'action-following-{patient.id}']=following
                focus(patient,'DONE:'+outcome)
            except ValueError as exc:st.error(str(exc))

def create(app,patient,view,kind):
    from executive_health_ai.ui.pages.manager import workflow
    st.subheader(kind)
    if not view.program:
        st.info('先建立有负责人和年度归属的计划，再安排管理工作。')
        from executive_health_ai.ui.pages.manager.experience import management
        management(app,patient,action='建立 / 调整计划');return
    if kind=='新增管理记录':workflow.logs(patient,view);return
    if kind=='安排复查':workflow.recheck_create(patient,view,expanded=True);return
    if kind=='提交医生判断':
        st.caption('进入现有医学判断与会诊申请；医生负责意见和医学决定。')
        workflow.consultations(app,patient);return
    if kind=='申请服务':
        from executive_health_ai.services.member_services import MemberServiceOperations
        with SessionLocal() as session:catalog=list(session.scalars(select(ServiceCatalogItem).order_by(ServiceCatalogItem.name)))
        if not catalog:st.info('服务目录尚未配置，可先创建协调随访。');quick_actions(patient);return
        with st.form('action-service-request'):
            item=st.selectbox('申请服务项目',catalog,format_func=lambda r:r.name)
            reason=st.text_area('申请原因')
            submit=st.form_submit_button('提交服务申请',type='primary')
        if submit:
            try:
                if not reason.strip():raise ValueError('请填写申请原因。')
                with SessionLocal() as session:
                    row=MemberServiceOperations().request(session,patient.id,item.id,reason,view.owner)
                    if row.program_id and row.program_id!=view.program.id:raise ValueError('已有另一年度的同类服务申请，请先在该周期处理。')
                    workflow.service.link_service(session,patient.id,row.id,view.program.id,view.current_phase.id if view.current_phase else None)
                    identity='SERVICE:'+str(row.id);session.commit()
                focus(patient,identity)
            except ValueError as exc:st.error(str(exc))
        return
    from executive_health_ai.services import care_commands
    with st.form('action-followup-create'):
        title=st.text_input('随访事项',value='阶段健康随访');instruction=st.text_area('需要跟进什么')
        due=st.date_input('下次跟进日期',value=date.today()+timedelta(days=7));owner=st.text_input('负责人',value=view.owner)
        submit=st.form_submit_button('创建随访待办',type='primary')
    if submit:
        try:
            with SessionLocal() as session:
                row=care_commands.schedule_followup(session,session.get(HealthProgram,view.program.id),title=title,instruction=instruction,due_at=datetime.combine(due,time(9),ux.LOCAL),owner=owner)
                identity='FOLLOWUP:'+str(row.id) if '随访' in title else 'MANAGEMENT:'+str(row.id);session.commit()
            focus(patient,identity)
        except ValueError as exc:st.error(str(exc))

def stage_detail(patient,state):
    from executive_health_ai.ui.pages.manager import workflow
    phase=state['phase'];view=state['view']
    if not phase:st.info('先在年度方案与阶段中建立当前阶段。');quick_actions(patient);return
    st.subheader('阶段复盘 · '+phase.title)
    if not state['review']:
        if not state['review_ready']:st.info('当前尚未满足复盘条件。');quick_actions(patient);return
        st.caption('以下是从已有记录整理的草稿，不代表 AI 医学判断；请健管核对。')
        workflow.stage_metrics(patient,view,phase)
        draft=service.stage_summary(state)
        with st.form('action-stage-review'):
            content={k:st.text_area(k,value=v) for k,v in draft.items()}
            medical=st.checkbox('未解决问题需要医生判断')
            confirm=st.checkbox('我已核对阶段结果，确认本次复盘')
            submit=st.form_submit_button('确认阶段总结',type='primary')
        if submit:
            try:
                if not confirm:raise ValueError('请先勾选阶段结果核对确认。')
                with SessionLocal() as session:
                    service.review_stage(session,patient.id,view.program.id,phase_id=phase.id,content=content,actor=view.owner,medical=medical);session.commit()
                st.rerun()
            except ValueError as exc:st.error(str(exc))
        return
    st.success('阶段总结已确认，下一阶段草稿已准备。')
    draft=service.next_phase_draft(state)
    st.write('重点关注：'+state['review'].content.get('下一阶段建议','待健管填写'))
    st.caption('复查与服务：仅沿用已存在的安排；新的医学复查仍需正式医疗依据。')
    def planned(row):
        at=getattr(row,'due_at',None) or getattr(row,'planned_at',None) or getattr(row,'scheduled_at',None)
        return bool(draft['existing'] and getattr(row,'phase_id',None)==draft['existing'].id or
            getattr(row,'program_id',None)==view.program.id and at and draft['start']<=at.date()<=draft['end'])
    plans=[{'类型':'管理事项','安排':r.title,'状态':status_label(r.status)} for r in view.tasks if planned(r)]
    plans += [{'类型':'复查','安排':r.title,'状态':status_label(r.status)} for r in view.rechecks if planned(r)]
    plans += [{'类型':'服务','安排':r.reason,'状态':status_label(r.status)} for r in view.services if planned(r)]
    if plans:st.dataframe(pd.DataFrame(plans),hide_index=True,width='stretch')
    else:st.info('下一阶段尚无已有复查或服务安排；下面确认第一件管理事项，其余可在进入阶段后继续创建。')
    with st.form('action-next-phase-confirm'):
        title=st.text_input('下一阶段名称',value=draft['title'],disabled=bool(draft['existing']))
        goal=st.text_area('下一阶段目标',value=draft['goal'],disabled=bool(draft['existing']))
        content=st.text_area('下一阶段管理内容',value=draft['content'],disabled=bool(draft['existing']))
        start=st.date_input('下一阶段开始',value=draft['start'],disabled=bool(draft['existing']))
        end=st.date_input('下一阶段结束',value=draft['end'],disabled=bool(draft['existing']))
        action=st.text_input('下一阶段第一件管理事项',value='确认下一阶段执行安排')
        submit=st.form_submit_button('确认并进入下一阶段',type='primary')
    if submit:
        try:
            with SessionLocal() as session:
                service.enter_next_phase(session,patient.id,view.program.id,phase.id,actor=view.owner,title=title,goal=goal,content=content,start=start,end=end,action=action);session.commit()
            focus(patient,'NEXT')
        except ValueError as exc:st.error(str(exc))
