"""Care workbench composition. All facts and commands use the existing services."""
from datetime import datetime
import streamlit as st
from executive_health_ai.database import SessionLocal
from executive_health_ai.services.product_projection import ProductProjectionService
from executive_health_ai.services.information_presentation import member_directory
from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.presentation import data_table, preview, work_filter, WORK_FILTERS
from executive_health_ai.ui.status_dictionary import status_label


def today(app):
    if st.session_state.get('care-detail'):
        from executive_health_ai.ui.pages.manager.post_checkup import manager_detail
        manager_detail(app, st.session_state['care-detail'])
        return
    from executive_health_ai.ui.pages.manager.assistant import assistant, progress
    now = datetime.now(ux.LOCAL)
    people = app._patient_map()
    with SessionLocal() as session:
        work = ProductProjectionService().manager(session, now)
        from executive_health_ai.services.autonomy_projection import oversight
        automatic = oversight(session, now)
        from executive_health_ai.models import RiskEvent
        from sqlalchemy import select
        attention_ids = set(session.scalars(select(RiskEvent.id).where(RiskEvent.risk_level == 'YELLOW')))
        from executive_health_ai.models import Task
        from executive_health_ai.services.operational_worklist import OperationalWorkItem
        history=[OperationalWorkItem(t.patient_id,'task',t.id,9,'已完成',t.title,t.instruction or '',
            '查看已记录结果',t.completed_at,owner=t.assignee or '待分配') for t in session.scalars(select(Task).where(
                Task.patient_id.in_(list(people)),Task.status=='COMPLETED').order_by(Task.completed_at.desc()))]
    items = ux.sorted_work(work.items, now)
    selected = st.session_state.get('today-detail')
    if selected:
        if st.button('← 返回今日工作'):
            st.session_state.pop('today-detail', None)
            st.session_state['today-work-grid-epoch'] = st.session_state.get('today-work-grid-epoch', 0)+1
            st.rerun()
        item = next((i for i in items+history if (i.source_type, str(i.source_id)) == selected), None)
        if item:
            work_detail(app, item, people.get(item.member_id))
        else:
            st.success('本次处理已完成，后续需要您处理的事情会重新进入今日工作。')
        return
    c.page_shell('manager', '今日工作','从待办开始，完成后继续下一项。')
    main,rail=st.columns([3.25,1],gap='large')
    with main,st.container(key='v7-main-today'):
        st.subheader('当前工作队列')
        exceptional=work_filter(items,'逾期',now)
        groups={'全部':items+history,'待处理':items,'异常':list({(i.source_type,i.source_id):i for i in exceptional+[i for i in items if i.priority<=1]}.values()),'已完成':history}
        bucket=st.radio('事项范围',list(groups),index=1,horizontal=True,format_func=lambda label:label+' '+str(len(groups[label])),key='v7-work-bucket')
        selected_items=groups[bucket]
        with st.container(key='soft-filter-today'):
            a,b,d = st.columns([1,2,1])
            scope = a.selectbox('工作筛选', ['全部','今天','需关注','医疗','复查','服务','管理','逾期','等待医生','等待会员'], key='v5-work-scope')
            search = b.text_input('查找待办', placeholder='搜索会员或需要处理的事情', key='v2-work-search').strip().casefold()
            owner = d.selectbox('负责人', ['全部']+sorted({i.owner or '待分配' for i in items}), key='today-owner')
        if scope == '需关注':
            scoped = [i for i in selected_items if i.source_type == 'risk_event' and i.source_id in attention_ids]
        else:
            scoped = work_filter(selected_items,scope,now) if scope not in {'医疗','管理'} else [i for i in selected_items if
                (i.source_type in {'doctor_review','consultation','baseline_review','legacy_medical_review','risk_event'}) == (scope=='医疗')]
        visible = [i for i in scoped if (owner=='全部' or (i.owner or '待分配')==owner)
            and (not search or search in (app._member_display(people.get(i.member_id))+i.title+i.reason+i.next_action).casefold())]
        item = data_table(visible, [{'会员':app._member_display(people.get(i.member_id)), '事项':i.title, '当前阶段':progress(i), '负责人':i.owner,
            '时间':ux.local_time(i.due_at), '状态':('优先处理 · ' if i.priority == 0 else '') + (status_label(i.status,context='service_request') if i.source_type=='service_request' else status_label(i.status))} for i in visible],
            key='today-work-grid', auto_select=False, activate_on_cell=True, empty='当前没有需要处理的工作。')
        if item:
            if item.source_type in {'post_checkup','profile_intake'}:
                st.session_state['care-detail'] = str(item.source_id)
                st.session_state['care-origin'] = '今日工作'
            else:
                st.session_state['today-detail'] = (item.source_type, str(item.source_id))
            st.rerun()
    with rail,st.container(key='v7-context-today'):
        st.subheader('工作概况')
        c.summary_strip([('待处理',len(items)),('逾期',len(work_filter(items,'逾期',now))),('等待医生',len(work.pending_doctor))])
        st.caption(f"自动管理 {automatic['managed']} · 无需人工 {automatic['no_human']} · 需关注 {automatic['attention']} · 优先处理 {automatic['urgent']}")
        st.divider()
        st.markdown('**我的待办**')
        for i in items[:3]:
            st.caption(app._member_display(people.get(i.member_id))+' · '+ux.business_text(i.title)+' · '+ux.when(i.due_at))
        st.divider()
        st.markdown('**快捷动作**')
        if st.button('新会员',key='today-enroll'):
            st.session_state['v7-enroll-open']=True
            app.request_navigation(surface='运营后台',ops_page='成员')
        st.divider()
        assistant(app,people)


def work_detail(app, item, member):
    from executive_health_ai.ui.pages.manager import workflow
    from executive_health_ai.ui.pages.manager.assistant import progress
    from sqlalchemy import select
    from executive_health_ai.models import Task, ServiceRequest, DoctorReview, RiskEvent
    st.header(app._member_display(member)+' · '+ux.business_text(item.title))
    c.summary_strip([('当前状态',status_label(item.status)),('负责人',item.owner or '待分配'),('截止时间',ux.when(item.due_at))])
    st.subheader('现在需要你做')
    st.write(ux.business_text(item.next_action))
    if not member:
        st.warning('会员资料暂不可用，请联系管理员。'); return
    view = workflow.view_for(member.id)
    if item.source_type=='management_setup':
        from executive_health_ai.ui.pages.manager.goal_loop import gate
        gate(app,member,view)
        return
    with SessionLocal() as session:
        task = session.get(Task,item.source_id) if item.source_type=='task' else None
        request = session.get(ServiceRequest,item.source_id) if item.source_type=='service_request' else None
    if task:
        if task.status not in {'COMPLETED','CANCELLED'} and view.program:
            from executive_health_ai.services.management_action_loop import ManagementActionLoop
            with SessionLocal() as session:state=ManagementActionLoop().project(session,member.id,view.program.id)
            actual=next((i for i in state['items'] if i.record.id==task.id),None)
            if actual:
                st.session_state[f'action-focus-{member.id}']=actual.id
                st.session_state['member-return-origin']='今日工作'
                app.request_navigation(surface='运营后台',ops_page='成员',member_id=member.id,member_section='管理')
                return
        from executive_health_ai.ui.presentation import task_action
        task_action(app,task)
    elif request:
        from executive_health_ai.ui.pages.manager.services import service_detail
        service_detail(app,request,member)
    elif item.source_type=='recheck':
        workflow.recheck(patient=member,view=view,selected_id=item.source_id)
    elif item.source_type=='stage_review':
        st.session_state[f'action-focus-{member.id}']='STAGE_REVIEW'
        st.session_state['member-return-origin']='今日工作'
        app.request_navigation(surface='运营后台',ops_page='成员',member_id=member.id,member_section='管理')
        return
    elif item.source_type=='consultation':
        workflow.consultations(app,member,selected_id=item.source_id)
    elif item.source_type in {'doctor_review','baseline_review','legacy_medical_review'}:
        from executive_health_ai.ui.pages.manager.medical import review_detail
        review_detail(app,member,item.source_id,item.source_type)
    elif item.source_type=='intake_review':
        from executive_health_ai.models.management_workflow import IntakeAssessment
        with SessionLocal() as session:
            intake=session.get(IntakeAssessment,item.source_id)
        if intake and intake.patient_id==member.id and intake.status=='DRAFT':
            st.session_state['member-return-origin']='今日工作'
            st.session_state.pop(f'archive-content-{member.id}',None)
            app.request_navigation(surface='运营后台',ops_page='成员',member_id=member.id,member_section='健康')
            return
        workflow.intake(app,member,assessment_id=item.source_id)
    elif item.source_type=='risk_event':
        with SessionLocal() as session:
            risk = session.get(RiskEvent,item.source_id)
        app._render_current_risk_actions(member,selected_id=item.source_id)
    elif item.source_type=='report_review' and item.document_id:
        app.render_report_review(item.document_id)
    elif item.source_type=='automation_approval':
        from executive_health_ai.ui.pages.manager.experience import approvals
        approvals(app,member.id,selected_id=item.source_id)
    else:
        if st.button('查看会员相关资料',type='primary'):
            st.session_state['member-return-origin']='今日工作'
            app._open_member_management(member.id)
    st.subheader('系统已经完成')
    st.write(progress(item))
    with st.expander('关键信息 / 数据 / 依据'):
        st.write(ux.business_text(item.reason))
        data_table(view.documents,[{'报告':d.title,'时间':ux.local_time(d.created_at)} for d in view.documents],key='work-docs',selectable=False)
    st.subheader('接下来')
    st.write('系统保存本次处理结果；后续需要人工处理的事情会进入今日工作，完整记录保留在会员360。')
    if st.button('进入会员360'):
        st.session_state['member-return-origin']='今日工作'
        app._open_member(member.id)


def open_directory_member(app, member):
    st.session_state['member-return-origin']='会员'
    st.session_state['member-directory-epoch']=st.session_state.get('member-directory-epoch',0)+1
    app.request_navigation(ops_page='成员',member_id=member.id,member_section='概览',rerun=False)


def directory(app, members):
    from executive_health_ai.ui.pages.manager import workflow
    c.page_shell('manager','会员','搜索和筛选会员，找到某个人，进入 Member360 概览。')
    # Always reserve the feedback slot: an optional success message used to
    # shift the filter block's delta path and briefly retain its old DOM copy.
    with st.container(key='member-directory-feedback'):
        workflow.flash()
    with SessionLocal() as session:
        rows = member_directory(session, members, include_archived=True)
    query, state, owner = c.filter_bar(key='member-list', search_label='搜索成员',
        statuses=['在管','已归档','全部'], all_statuses=False,
        owners=sorted({r['program'].owner if r['program'] else '待分配' for r in rows}))
    scope = (query, state, owner)
    if st.session_state.get('member-directory-scope') != scope:
        st.session_state['member-directory-scope'] = scope
        st.session_state['member-directory-epoch'] = st.session_state.get('member-directory-epoch', 0)+1
    workflow.enroll(app)
    rows = [r for r in rows if (not query or query in (app._member_display(r['member'])+r['focus']).casefold())
            and (state=='全部' or state==('已归档' if r['member'].archived_at else '在管'))
            and (owner=='全部' or owner==(r['program'].owner if r['program'] else '待分配'))]
    records=[]
    now=datetime.now(ux.LOCAL).date()
    for r in rows:
        p,t,phase,log = r['program'],r['task'],r['phase'],r['log']
        person=r['member'];born=person.birth_date
        age=str(now.year-born.year-((now.month,now.day)<(born.month,born.day))) if born else '未记录'
        records.append({'会员':app._member_display(person), '年龄 / 性别':age+' / '+{'male':'男','female':'女','MALE':'男','FEMALE':'女'}.get(person.sex,'未记录'),
            '当前阶段':phase.title if phase else app.display_program_phase(p.current_phase) if p else '待建档',
            '责任健管':p.owner if p else '待分配','当前服务':r['service'],
            '下一行动':'查看历史资料（只读）' if person.archived_at else t.title if t else '待确认安排',
            '状态':'已归档' if person.archived_at else status_label(p.status) if p else '待建档',
            '操作':'—' if person.archived_at else '删除'})
    from executive_health_ai.ui.pages.manager.member_delete import request_delete, pending_confirmation
    chosen = data_table(rows, records, cell_actions={'操作':lambda row:request_delete(row['member'])}, key='member-directory',label='选择会员',empty='未找到匹配会员。',auto_select=False,activate_on_cell=True)
    if chosen:
        open_directory_member(app,chosen['member']);st.rerun()
    pending_confirmation()


def archive(app, patient, view):
    from executive_health_ai.ui.pages.manager.goal_loop import provenance
    provenance(patient.id)
    from executive_health_ai.ui.pages.manager import workflow
    from executive_health_ai.ui.pages.manager import intake_entry
    section_key=f'archive-content-{patient.id}'
    selected=st.session_state.get(section_key)
    if selected=='完整档案':
        if st.button('← 返回健康档案主页'):
            st.session_state.pop(section_key,None);st.rerun()
        full_archive(app,patient,view)
        return
    if selected:
        if selected=='初始评估':
            workflow.intake(app,patient)
            return
        if st.button('← 返回健康档案摘要',key=section_key+'-back'):
            st.session_state.pop(section_key,None)
            st.session_state[section_key+'-epoch']=st.session_state.get(section_key+'-epoch',0)+1;st.rerun()
        if selected=='医疗档案':app._render_client_medical_archive(patient)
        elif selected=='家庭关系':workflow.family(patient,view)
        elif selected in {'报告','基线','健康数据'}:
            desired={'报告':'体检','基线':'基线','健康数据':'数据'}[selected]
            st.session_state[f'member-health-view-{patient.id}']=desired
            app.render_member_archive(patient,selected_view=desired)
        else:
            value=(view.intake.responses if view.intake else {}).get(selected)
            st.subheader(selected)
            if view.intake and intake_entry.state(view.intake) != '已完成':
                st.caption('会员自述 · 尚待健管确认')
            if isinstance(value,list) and value:data_table(value,value,key=section_key+'-answers',selectable=False)
            elif isinstance(value,dict) and value:
                data_table(list(value),[{'项目':k,'记录':v or '待补充'} for k,v in value.items()],key=section_key+'-answers',selectable=False)
            else:
                st.caption('暂无已确认记录。')
                st.button('去补充初始评估',key=section_key+'-intake',on_click=intake_entry.amend,
                    args=(patient,view),kwargs={'step':selected})
        return
    from executive_health_ai.ui.pages.manager import intake_workspace
    data=intake_workspace.workspace(app,patient,view)
    with st.expander("完整查看 / 手工修正",expanded=False):
        intake_workspace.cards(patient,view,data)
    if st.button('查看完整健康档案',key=f'full-archive-{patient.id}'):
        st.session_state[section_key]='完整档案';st.rerun()


def full_archive(app,patient,view):
    from executive_health_ai.ui.pages.manager import profile_intake,intake_entry
    section_key=f'archive-content-{patient.id}'
    st.subheader('完整健康档案')
    profile_intake.confirmed_records(patient.id)
    responses=view.intake.responses if view.intake else {}
    entries=[('基础资料','基础资料','已建档'),('家族史','家族健康史',None),('既往史','个人病史',None),
        ('手术 / 住院','手术 / 住院史',None),('过敏','过敏史',None),('用药','当前用药 / 营养补充',None),
        ('最近用药','最近用药',None),('生活方式','生活方式',None),('环境暴露','环境与暴露',None),
        ('会员关注','会员重点关注',view.intake.member_concern if view.intake else '待填写'),
        ('专项症状','专项症状评估',None),('已确认医疗档案','医疗档案','病史、过敏、用药与手术记录'),
        ('家庭关系与紧急联系人','家庭关系',str(len(view.family))+' 项'),('体检报告','报告',str(sum(d.document_type not in {'questionnaire','history'} for d in view.documents))+' 份'),
        ('年度健康基线','基线','查看已确认基线'),('健康数据','健康数据','查看持续变化趋势')]
    rows=[]
    for title,key,summary in entries:
        value=responses.get(key)
        rows.append({'title':title,'key':key,'summary':summary or (f'{len(value)} 项记录' if isinstance(value,list) and value else '已填写' if value else '待补充')})
    st.caption('完整资料、原始文件及导入历史保留于此。正式医疗档案仍遵守原有确认要求。')
    with st.container(key='soft-archive-details'):
        chosen=data_table(rows,[{'资料':r['title'],'摘要':r['summary']} for r in rows],key=section_key,auto_select=False,activate_on_cell=True)
        if chosen:
            st.session_state[section_key]=chosen['key'];st.rerun()
    profile_intake.history(app,patient)


def medical(app, patient):
    from executive_health_ai.ui.pages.manager.medical import collaboration
    from executive_health_ai.ui.pages.manager import workflow
    mode=st.radio('医疗工作',['医学判断与会诊','医疗记录','申请会诊','转诊'],horizontal=True,key=f'care-medical-{patient.id}')
    if mode=='医学判断与会诊':collaboration(app,patient)
    elif mode=='医疗记录':app.render_member_medical_workspace(patient,app._member_medical_context(patient.id))
    elif mode=='申请会诊':workflow.consultations(app,patient)
    else:app.render_external_doctor_workspace([patient])
