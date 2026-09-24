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
    c.page_shell('manager', '今日工作', '今天需要处理谁、为什么、何时完成，以及下一步。')
    now = datetime.now(ux.LOCAL)
    people = app._patient_map()
    with SessionLocal() as session:
        work = ProductProjectionService().manager(session, now)
    items = ux.sorted_work(work.items, now)
    c.summary_strip([('今日待办', len(work_filter(items, '今天', now))), ('已逾期', len(work_filter(items, '逾期', now))),
                     ('等待医生', len(work_filter(items, '等待医生', now))), ('等待会员', len(work_filter(items, '等待会员', now))),
                     ('待复查', len(work_filter(items, '复查', now)))])
    categories = {'全部事项': None, '入组初评':'intake_review', '复查':'recheck', '阶段复盘':'stage_review',
                  '正式会诊':'consultation', '体检':'report_review', '风险':'risk_event', '医生':'doctor_review',
                  '计划 / 复查':'task', '服务':'service_request', '自动跟进':'automation_approval'}
    a,b,d = st.columns([1,2,1])
    kind = a.selectbox('今日事项筛选', list(categories), key='manager-today-filter')
    search = b.text_input('查找待办', placeholder='输入会员、事项或原因', key='v2-work-search').strip().casefold()
    owner = d.selectbox('负责人', ['全部']+sorted({i.owner or '待分配' for i in items}), key='today-owner')
    scope = st.radio('处理范围', WORK_FILTERS, horizontal=True, key='today-range')
    visible = [i for i in work_filter(items, scope, now)
               if (kind=='全部事项' or i.source_type==categories[kind] or kind=='医生' and i.status=='等待医生')
               and (owner=='全部' or (i.owner or '待分配')==owner)
               and (not search or search in (app._member_display(people.get(i.member_id))+i.title+i.reason+i.next_action).casefold())]
    st.subheader('管理事项')
    if not visible:
        c.empty_state('当前筛选下暂无事项', '切换类型或调整搜索查看其他待办。')
        return
    item = data_table(visible, [{'会员':app._member_display(people.get(i.member_id)), '事项':i.title,
        '类型':i.source_label, '优先级':'高' if i.priority<=1 else '中' if i.priority==2 else '低',
        '状态':status_label(i.status, context='service_request') if i.source_type=='service_request' else status_label(i.status),
        '负责人':i.owner, '截止时间':ux.local_time(i.due_at), '下一步':i.next_action} for i in visible],
        key='today-work-grid', label='选择待办', auto_select=False)
    if item:
        with c.detail_drawer('事项详情', key='today', table_key='today-work-grid'):
            work_detail(app, item, people.get(item.member_id))
    # Retained operational waiting state, subordinate to today's business queue.
    from sqlalchemy import select
    from executive_health_ai.models import AgentGoal
    with SessionLocal() as session:
        goals=list(session.scalars(select(AgentGoal).where(AgentGoal.status.in_(('ACTIVE','WAITING','BLOCKED')))))
    if goals:
        with st.expander('自动跟进状态'):
            goal=data_table(goals,[{'目标':g.title,'阶段':g.current_stage,'负责人':g.owner,'下一步':g.next_action} for g in goals],key='today-auto',auto_select=False)
            if goal:
                st.write(ux.business_text(goal.next_action))
                if st.button('处理确认',key=f'ux-goal-open-{goal.id}'):
                    st.session_state[f'workflow-mode-{goal.member_id}']='原有计划 / 任务 / 自动跟进'
                    app._open_member_management(goal.member_id)


def work_detail(app, item, member):
    from executive_health_ai.ui.pages.manager import workflow
    st.markdown('### '+ux.business_text(item.title))
    c.summary_strip([('当前状态',status_label(item.status)),('优先级','高' if item.priority<=1 else '中'),
                     ('负责人',item.owner or '待分配'),('截止时间',ux.when(item.due_at))])
    st.info('下一步：'+preview(item.next_action,80))
    st.markdown('**发生了什么**'); st.write(ux.business_text(item.source_label+' · '+item.title))
    st.markdown('**为什么要处理**'); st.write(ux.business_text(item.reason or '核对现有安排，明确后续执行。'))
    if member:
        view = workflow.view_for(member.id)
        with SessionLocal() as session:
            context = ProductProjectionService().member(session, member.id, health=True)
            evidence = app._risk_evidence_payload(session, member.id, item.source_id) if item.source_type=='risk_event' else None
        st.markdown('**关键数据**')
        series = [s for s in context.health.series if s.points][:4]
        data_table(series, [{'指标':s.label, '当前值':f'{s.points[-1].value:g} {s.unit}', '时间':ux.local_time(s.points[-1].at)} for s in series], key='today-key-data', selectable=False, empty='尚无已确认数值记录。')
        with st.expander('相关报告 / 依据'):
            if evidence:
                ux.evidence_summary(evidence)
                app._render_evidence_action(evidence, key_scope=f'today-evidence-{item.source_id}')
            data_table(view.documents, [{'报告':r.title,'时间':ux.local_time(r.created_at)} for r in view.documents], key='today-evidence-docs', selectable=False)
            ux.baseline_summary(context.baseline, context.observations, compact=True)
        with st.expander('最近管理记录'):
            workflow.log_rows(view.logs[:2], key='today-recent-log')
    st.markdown('**下一步**'); st.write(ux.business_text(item.next_action))
    label = {'task':'处理当前任务','report_review':'确认体检资料','recheck':'处理复查安排','stage_review':'记录阶段结果',
             'intake_review':'确认初始评估','service_request':'跟进服务','consultation':'查看会诊','doctor_review':'查看医生协同',
             'risk_event':'处理关注事项','automation_approval':'确认后续安排'}.get(item.source_type,'查看成员详情')
    if st.button(label, key=f'today-{item.source_type}-{item.source_id}', type='primary', width='stretch'):
        if item.source_type=='report_review' and item.document_id:
            app._open_report_review_from_worklist(item.member_id, item.document_id)
        elif item.source_type=='intake_review':
            st.session_state[f'workflow-record-{item.member_id}']='初始评估'
            app.request_navigation(surface='运营后台',ops_page='成员',member_id=item.member_id,member_section='健康')
        elif item.source_type in {'doctor_review','consultation'} or item.route_target=='doctor_review':
            if item.source_type=='consultation': st.session_state[f'care-medical-{item.member_id}']='正式会诊'
            app.request_navigation(surface='运营后台',ops_page='成员',member_id=item.member_id,member_section='医疗')
        elif item.route_target=='member_service': app._open_member_service(item.member_id)
        else:
            mode={'recheck':'检查复查','stage_review':'阶段评估','automation_approval':'原有计划 / 任务 / 自动跟进'}.get(item.source_type,'管理事项')
            st.session_state[f'workflow-mode-{item.member_id}']=mode
            app._open_member_management(item.member_id)


def directory(app, members):
    from executive_health_ai.ui.pages.manager import workflow
    c.page_shell('manager','会员','按年度进度找到会员，进入 Member 360 处理。')
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
    records=[]
    for r in rows:
        p,t,phase,log = r['program'],r['task'],r['phase'],r['log']
        records.append({'会员':app._member_display(r['member']), '当前年度':f'{p.start_date:%Y/%m}—{p.end_date:%Y/%m}' if p else '待建档',
            '当前阶段':phase.title if phase else app.display_program_phase(p.current_phase) if p else '待建档',
            '主要管理重点':r['focus'] or '待初评','责任健管':p.owner if p else '待分配',
            '最近联系':ux.local_time(log.occurred_at) if log else None,'下一事项':t.title if t else '待确认安排',
            '下一日期':ux.local_time(t.due_at) if t else None,'状态':status_label(p.status) if p else '待建档'})
    chosen = data_table(rows, records, key='member-directory',label='选择会员',empty='未找到匹配会员。',auto_select=False,activate_on_cell=True)
    if chosen:
        st.session_state['member-directory-epoch'] = st.session_state.get('member-directory-epoch', 0)+1
        app._open_member(chosen['member'].id)
        st.rerun()


def archive(app, patient, view):
    """A compact archive index; source responses and original medical tools stay reachable."""
    mode=st.radio('健康档案内容',['健康资料与趋势','初始评估'],horizontal=True,key=f'workflow-record-{patient.id}')
    from executive_health_ai.ui.pages.manager import workflow
    if mode=='初始评估':
        workflow.intake(app,patient)
        return
    archive_key=f'member-health-view-{patient.id}'
    if st.session_state.get(archive_key) in {'数据','体检','基线','健康史'}:
        if st.button('返回档案摘要',key=f'archive-summary-back-{patient.id}'):
            st.session_state[archive_key]='概览';st.rerun()
        app.render_member_archive(patient)
        return
    st.subheader('健康档案摘要')
    responses=view.intake.responses if view.intake else {}
    mapping=[('基础资料','基础资料'),('家族史','家族健康史'),('个人病史','个人病史'),('手术 / 住院','手术 / 住院史'),
             ('过敏','过敏史'),('用药','当前用药 / 营养补充'),('最近用药','最近用药'),('生活方式','生活方式'),
             ('环境暴露','环境与暴露'),('会员重点关注','会员重点关注'),('专项症状评估','专项症状评估')]
    for col, group in zip(st.columns(2), [mapping[:6],mapping[6:]]):
        with col:
            for title, source in group:
                value=responses.get(source)
                summary = f'{len(value)} 项自述' if isinstance(value,list) and value else '已填写' if value else '待补充'
                if source=='会员重点关注': summary=preview(view.intake.member_concern,28) if view.intake else '待填写'
                with st.expander(title+' · '+summary):
                    if source=='基础资料':
                        st.write(patient.display_name);st.caption(f'出生日期：{patient.birth_date or "待补充"}')
                    elif isinstance(value,list):
                        data_table(value, value, key=f'archive-{patient.id}-{source}',selectable=False)
                    elif isinstance(value,dict):
                        for k,v in value.items():st.write(f'{k}：{v or "待补充"}')
                    else: st.caption('暂无已确认记录；可在初始评估中补充。')
    with st.expander('已确认医疗档案 · 用药 / 健康史 / 过敏 / 手术住院'):
        app._render_client_medical_archive(patient)
    workflow.family(patient,view)
    with st.expander(f'体检报告 · {len(view.documents)} 份'):
        doc=data_table(view.documents,[{'报告':d.title,'日期':ux.local_time(d.created_at),'状态':status_label(d.status)} for d in view.documents], key=f'archive-reports-{patient.id}')
        if doc:
            st.button('查看报告',key=f'archive-open-report-{patient.id}',on_click=app._open_report_review_from_worklist,args=(patient.id,doc.id))
        app.render_report_upload(patient,key_prefix=f'archive-upload-{patient.id}')
    with st.expander('年度健康基线与健康数据', expanded=False):
        app.render_member_archive(patient)


def medical(app, patient):
    from executive_health_ai.ui.pages.manager import workflow
    mode=st.radio('医疗协同工作',['医生复核','正式会诊','医疗档案','转诊'],horizontal=True,key=f'care-medical-{patient.id}')
    if mode=='正式会诊':workflow.consultations(app,patient)
    elif mode=='转诊':app.render_external_doctor_workspace([patient])
    elif mode=='医疗档案':app.render_member_medical_workspace(patient,app._member_medical_context(patient.id))
    else:
        from executive_health_ai.ui.pages.doctor.experience import workspace
        workspace(app,[patient],patient=patient,read_only=True)
