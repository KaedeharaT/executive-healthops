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
    items = ux.sorted_work(work.items, now)
    selected = st.session_state.get('today-detail')
    if selected:
        if st.button('← 返回今日工作'):
            st.session_state.pop('today-detail', None)
            st.session_state['today-work-grid-epoch'] = st.session_state.get('today-work-grid-epoch', 0)+1
            st.rerun()
        item = next((i for i in items if (i.source_type, str(i.source_id)) == selected), None)
        if item:
            work_detail(app, item, people.get(item.member_id))
        else:
            st.success('本次处理已完成，后续需要您处理的事情会重新进入今日工作。')
        return
    with st.container(key='neu-today-summary'):
        heading, summary = st.columns([1, 3.2], vertical_alignment='center')
        with heading:
            c.page_shell('manager', '今日工作', '今天我需要处理什么？')
        with summary:
            c.summary_strip([('待我处理',sum(i.status not in {'等待医生','等待成员','等待会员'} for i in items)),
                ('已逾期',len(work_filter(items,'逾期',now))),('等待医生',len(work.pending_doctor)),
                ('等待会员',len(work_filter(items,'等待会员',now))),('今天到期',len(work_filter(items,'今天',now)))])
    with st.container(key='neu-assistant'):
        assistant(app, people)
    with st.container(key='neu-work'):
        st.subheader('工作事项')
        with st.container(key='soft-filter-today'):
            a,b,d = st.columns([1,2,1])
            scope = a.selectbox('工作筛选', ['全部','今天','医疗','复查','服务','管理','逾期','等待医生','等待会员'], key='v5-work-scope')
            search = b.text_input('查找待办', placeholder='搜索会员或需要处理的事情', key='v2-work-search').strip().casefold()
            owner = d.selectbox('负责人', ['全部']+sorted({i.owner or '待分配' for i in items}), key='today-owner')
        scoped = work_filter(items,scope,now) if scope not in {'医疗','管理'} else [i for i in items if
            (i.source_type in {'doctor_review','consultation','baseline_review','legacy_medical_review','risk_event'}) == (scope=='医疗')]
        visible = [i for i in scoped if (owner=='全部' or (i.owner or '待分配')==owner)
            and (not search or search in (app._member_display(people.get(i.member_id))+i.title+i.reason+i.next_action).casefold())]
        item = data_table(visible, [{'会员':app._member_display(people.get(i.member_id)), '现在发生什么':i.title,
            '系统已经做到哪':progress(i), '现在需要我做什么':i.next_action, '负责人':i.owner,
            '截止时间':ux.local_time(i.due_at), '状态':status_label(i.status,context='service_request') if i.source_type=='service_request' else status_label(i.status)} for i in visible],
            key='today-work-grid', auto_select=False, activate_on_cell=True, empty='当前没有需要处理的工作。')
        if item:
            if item.source_type in {'post_checkup','profile_intake'}:
                st.session_state['care-detail'] = str(item.source_id)
                st.session_state['care-origin'] = '今日工作'
            else:
                st.session_state['today-detail'] = (item.source_type, str(item.source_id))
            st.rerun()


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
    with SessionLocal() as session:
        task = session.get(Task,item.source_id) if item.source_type=='task' else None
        request = session.get(ServiceRequest,item.source_id) if item.source_type=='service_request' else None
    if task:
        from executive_health_ai.ui.presentation import task_action
        task_action(app,task)
    elif request:
        from executive_health_ai.ui.pages.manager.services import service_detail
        service_detail(app,request,member)
    elif item.source_type=='recheck':
        workflow.recheck(patient=member,view=view,selected_id=item.source_id)
    elif item.source_type=='stage_review':
        workflow.stage_review(member,view)
    elif item.source_type=='consultation':
        workflow.consultations(app,member,selected_id=item.source_id)
    elif item.source_type in {'doctor_review','baseline_review','legacy_medical_review'}:
        from executive_health_ai.ui.pages.manager.medical import review_detail
        review_detail(app,member,item.source_id,item.source_type)
    elif item.source_type=='intake_review':
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
        rows = member_directory(session, members)
    c.summary_strip([('会员',len(rows)),('年度管理中',sum(bool(r['program']) for r in rows)),
                     ('有下一事项',sum(bool(r['task']) for r in rows))])
    query, state, owner = c.filter_bar(key='member-list', search_label='搜索成员',
        statuses=sorted({status_label(r['program'].status) if r['program'] else '待建档' for r in rows}),
        owners=sorted({r['program'].owner if r['program'] else '待分配' for r in rows}))
    scope = (query, state, owner)
    if st.session_state.get('member-directory-scope') != scope:
        st.session_state['member-directory-scope'] = scope
        st.session_state['member-directory-epoch'] = st.session_state.get('member-directory-epoch', 0)+1
    workflow.enroll(app)
    rows = [r for r in rows if (not query or query in (app._member_display(r['member'])+r['focus']).casefold())
            and (state=='全部' or state==(status_label(r['program'].status) if r['program'] else '待建档'))
            and (owner=='全部' or owner==(r['program'].owner if r['program'] else '待分配'))]
    with st.popover('会员管理'):
        st.caption('删除采用安全归档，需另外选择会员并输入姓名确认。')
        managed=st.selectbox('管理会员档案',[r['member'] for r in rows],index=None,
            format_func=app._member_display,key='directory-managed-member',placeholder='选择需要管理的会员')
        if managed:
            from executive_health_ai.ui.pages.manager.member_delete import actions
            actions(app,managed)
    records=[]
    for r in rows:
        p,t,phase,log = r['program'],r['task'],r['phase'],r['log']
        records.append({'会员':app._member_display(r['member']), '当前年度':f'{p.start_date:%Y/%m}—{p.end_date:%Y/%m}' if p else '待建档',
            '当前阶段':phase.title if phase else app.display_program_phase(p.current_phase) if p else '待建档',
            '主要管理重点':r['focus'] or '待初评','责任健管':p.owner if p else '待分配',
            '最近联系':ux.local_time(log.occurred_at) if log else None,'下一步':t.title if t else '待确认安排',
            '下一日期':ux.local_time(t.due_at) if t else None,'状态':status_label(p.status) if p else '待建档'})
    chosen = data_table(rows, records, key='member-directory',label='选择会员',empty='未找到匹配会员。',auto_select=False,activate_on_cell=True)
    if chosen:
        open_directory_member(app,chosen['member']);st.rerun()


def archive(app, patient, view):
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
