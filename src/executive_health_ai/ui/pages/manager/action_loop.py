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
    from executive_health_ai.services.autonomy_projection import member as autonomy_member
    with SessionLocal() as session:
        autonomy = autonomy_member(session, patient.id)
    if autonomy['level'] == 'RED':
        st.session_state['today-detail'] = ('risk_event', str(autonomy['risk_id']))
        app.request_navigation(surface='运营后台', ops_page='今日')
        return
    from executive_health_ai.ui.pages.manager.workflow import view_for
    from executive_health_ai.services.member_management_projection import onboarding_next
    view=view_for(patient.id)
    from executive_health_ai.services.management_goals import prerequisites
    with SessionLocal() as session:
        ready=prerequisites(session,session.get(HealthProgram,view.program.id) if view.program else None)
    if ready['intake'] and not ready['formal']:
        app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='管理')
        return
    with SessionLocal() as session:
        state=service.project(session,patient.id,view.program.id if view.program else None)
    onboarding=onboarding_next(view)
    if onboarding and not state['next']:
        destination=onboarding[1]
        st.session_state.pop(f'action-focus-{patient.id}',None)
        if destination in {'资料','初评','基线'}:
            st.session_state.pop(f'archive-content-{patient.id}',None)
            if destination=='基线':st.session_state[f'archive-content-{patient.id}']='基线'
            elif destination=='初评':
                from executive_health_ai.ui.pages.manager.intake_entry import open_intake
                open_intake(patient,view)
            app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='健康')
        else:
            if destination in {'方案','复查'}:st.session_state[f'workflow-mode-{patient.id}']='年度方案与阶段' if destination=='方案' else '检查复查'
            app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='医疗' if destination=='医疗' else '管理')
        return
    st.session_state[f'action-focus-{patient.id}']='NEXT'
    app.request_navigation(surface='运营后台',ops_page='成员',member_id=patient.id,member_section='管理')

def focus(patient,value):
    st.session_state[f'action-focus-{patient.id}']=value;st.rerun()

def clear(patient):
    st.session_state.pop(f'action-focus-{patient.id}',None);st.rerun()

def render(app,patient,view,*,show_recent=True,primary_next=True):
    from executive_health_ai.ui.pages.manager import workflow
    with SessionLocal() as session:
        state=service.project(session,patient.id,view.program.id if view.program else None)
        from executive_health_ai.services.autonomy_projection import member as autonomy_member
        autonomy = autonomy_member(session, patient.id)
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
    main,rail=st.columns([2.6,1],gap='large')
    with main,st.container(key='v7-main-management'):
        from executive_health_ai.ui.pages.manager.goal_loop import goal_status
        goal_status(patient.id,view.program.id if view.program else None)
        st.subheader('年度管理 · 当前阶段')
        workflow.phases(view)
        st.markdown('### '+(state['phase'].title if state['phase'] else '待安排阶段'))
        st.write(state['phase'].goal if state['phase'] else '建立阶段目标，并安排具体工作。')
        st.caption(f"核心事项完成 {sum(t.status=='COMPLETED' for t in state['planned'])} / {len(state['planned'])} · 表示执行进度，不是健康改善程度")
        st.subheader('待处理事项')
        item=data_table(state['items'],[{'事项':i.title,'类型':KINDS[i.kind],'计划时间':ux.local_time(i.due),'负责人':i.owner,'状态':status_label(i.status)} for i in state['items']],key=f'action-open-{patient.id}',auto_select=False,activate_on_cell=True,empty='当前还没有待处理事项。可记录本次沟通，或按阶段安排复盘。')
        if item:focus(patient,item.id)
        if show_recent:
            with st.expander('最近管理记录'):
                workflow.log_rows(view.logs[:3],key=f'action-recent-{patient.id}')
    with rail,st.container(key='v7-context-management'):
        st.subheader('当前行动')
        creation=()
        if autonomy['level'] == 'YELLOW':
            st.caption(':orange[需关注] ' + autonomy.get('reason', ''))
        if autonomy['level'] == 'RED':
            st.caption(':red[优先人工 / 医生处理]')
            st.write(autonomy['next_action'])
            st.caption('当前责任：' + autonomy['owner'])
            if st.button('处理', type='primary' if primary_next else 'secondary', key='action-immediate'):
                st.session_state['today-detail'] = ('risk_event', str(autonomy['risk_id']))
                app.request_navigation(surface='运营后台', ops_page='今日')
        elif state['next']:
            item=state['next'];st.write(item.title)
            st.caption(item.owner+' · '+ux.when(item.due))
            st.caption(item.next_action)
            if st.button('处理',type='primary' if primary_next else 'secondary',key='action-immediate'):focus(patient,item.id)
        elif state['review'] or state['review_ready']:stage_prompt(patient,state,primary=primary_next)
        else:
            from executive_health_ai.services.member_management_projection import onboarding_next
            onboarding=onboarding_next(view)
            if onboarding:
                st.write(onboarding[0])
                st.button('继续',key='management-empty-next',type='primary' if primary_next else 'secondary',on_click=open_next,args=(app,patient))
            else:
                st.caption('暂无开放事项。记录本次沟通结果，再安排后续工作。')
                if st.button('记录管理沟通',key='management-empty-log',type='primary' if primary_next else 'secondary'):focus(patient,'CREATE:新增管理记录')
                creation=('新增管理记录',)
        st.divider()
        if autonomy['level'] != 'RED':
            quick_actions(patient,exclude=creation)
    return False


def quick_actions(patient,*,exclude=()):
    from executive_health_ai.services.management_goals import prerequisites
    with SessionLocal() as session:
        view=service.project(session,patient.id)['view']
        if not prerequisites(session,session.get(HealthProgram,view.program.id) if view.program else None)['formal']:return
    with st.popover('新增安排'):
        labels=[label for label in ['新增管理记录','创建随访','安排复查','申请服务','提交医生判断'] if label not in exclude]
        label=st.selectbox('安排类型',labels,key='action-create-type')
        if st.button('继续',key='action-create-selected'):focus(patient,'CREATE:'+label)


def stage_prompt(patient,state,*,primary=True):
    if state['review']:
        st.info('阶段复盘已经完成，下一阶段草稿待确认。')
        if st.button('进入下一阶段',type='primary' if primary else 'secondary',key='action-next-phase'):focus(patient,'NEXT_PHASE')
    elif state['review_ready']:
        st.success('本阶段主要事项已完成' if state['all_done'] else '本阶段可以复盘；请核对未执行、取消或仍待处理的事项。')
        st.write('本阶段可以复盘 · 已整理完成事项、管理日志、复查与服务结果；指标变化使用已有健康数据。')
        if st.button('进行阶段复盘',type='primary' if primary else 'secondary',key='action-review'):focus(patient,'STAGE_REVIEW')

def detail(app,patient,view,item):
    from executive_health_ai.ui.pages.manager import workflow
    with st.container(border=True,key='soft-management-detail'):
        st.subheader('当前事项详情')
        st.markdown('### '+item.title)
        c.summary_strip([('来源',item.source),('负责人',item.owner),('截止时间',ux.when(item.due)),('状态',status_label(item.status))])
        st.write('为什么需要处理：'+item.reason)
        with st.expander('相关资料与依据'):
            st.write(ux.business_text(getattr(item.record,'evidence','') or getattr(item.record,'doctor_brief','') or item.reason))
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
        from executive_health_ai.ui.pages.manager.care_result_input import render as result_input
        result_input(patient,view,item,request_key)


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
    c.priority_strip('YELLOW','核对本阶段结果，再确认后续安排。',next_action='有未解决的医学问题时提交医生，其余按确认后的阶段计划继续。')
    from executive_health_ai.ui.pages.manager.care_runtime import for_phase
    for_phase(patient.id,phase.id)
    if not state['review']:
        if not state['review_ready']:st.info('当前尚未满足复盘条件。');quick_actions(patient);return
        st.caption('自动汇总已有记录；核对阶段结果，并确认下一阶段安排。医学问题仍交由医生判断。')
        workflow.stage_metrics(patient,view,phase)
        draft=service.stage_summary(state)
        following=service.next_phase_draft(state)
        medical=st.checkbox('未解决问题需要医生判断')
        can_advance=not medical and not state['phase_open'] and not any(r.status=='PENDING' for r in view.doctor_reviews)
        with st.form('action-stage-review'):
            main,rail=st.columns([2,1],gap='large')
            with main:
                for label,value in draft.items():
                    st.markdown('**'+label+'**');st.write(value)
                with st.expander('修正汇总内容与依据'):
                    content={k:st.text_area(k,value=v) for k,v in draft.items()}
            with rail:
                st.subheader('下一阶段')
                title=st.text_input('下一阶段名称',value=following['title'],disabled=bool(following['existing']))
                goal=st.text_area('下一阶段目标',value=following['goal'] or draft['下一阶段建议'],disabled=bool(following['existing']))
                action=st.text_input('下一阶段第一件管理事项',value='确认下一阶段执行安排')
                st.caption(str(following['start'])+' — '+str(following['end']))
                confirm=st.checkbox('我已核对阶段结果，确认本次复盘')
                submit=st.form_submit_button('确认并进入下一阶段' if can_advance else '确认复盘并提交医生' if medical else '确认阶段总结',type='primary')
        if submit:
            try:
                if not confirm:raise ValueError('请先勾选阶段结果核对确认。')
                with SessionLocal() as session:
                    service.review_stage(session,patient.id,view.program.id,phase_id=phase.id,content=content,actor=view.owner,medical=medical)
                    if can_advance:
                        session.flush()
                        service.enter_next_phase(session,patient.id,view.program.id,phase.id,actor=view.owner,title=title,goal=goal,
                            content=following['content'],start=following['start'],end=following['end'],action=action)
                    session.commit()
                if can_advance:focus(patient,'NEXT')
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
