"""Business-facing report preparation and medical handoff. No runtime controls."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from html import escape
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pandas as pd
import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentGoal, Document
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent import post_checkup as flow
from executive_health_ai.services.post_checkup import PostCheckupCareService
from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.presentation import data_table
from executive_health_ai.ui.charts.health import render_metric_trend
from executive_health_ai.services.health_visualization import HealthSeries, HealthPoint

KINDS = {'MANAGEMENT': '管理', 'FOLLOWUP': '随访', 'RECHECK': '复查', 'SERVICE': '服务'}


def command(goal_id, callback, *, activity="正在保存确认并继续后续管理", received=None, panel=None, current_stage=None):
    try:
        if panel is not None:
            header, progress = panel
            header.empty()
            st.markdown('<style>.st-key-care-human-action,.care-history .current,.care-history .next {display:none!important;}</style>', unsafe_allow_html=True)
        with (header.container() if panel is not None else st.container()):
            if panel is not None:
                c.summary_strip([('现在轮到','健康管理助手'),('当前状态','正在处理本次操作')])
            with st.status('健康管理助手继续工作', expanded=True) as running:
                if received:
                    st.write('✓ '+received)
                st.write('● 当前正在：'+activity)
                st.caption('系统正在实际处理本次操作，完成后自动进入下一步。')
                with SessionLocal() as session:
                    goal = session.get(AgentGoal, UUID(str(goal_id)))
                    if panel is not None:
                        with progress.container():
                            stepper(SimpleNamespace(current_stage=current_stage or goal.current_stage,
                                status='RUNNING', context_json=goal.context_json))
                    callback(session, goal)
                    session.commit()
                running.update(label='本次处理已保存，正在进入下一步', state='complete', expanded=False)
        st.rerun()
    except (ValueError, PermissionError) as exc:
        if panel is not None:
            st.markdown('<style>.st-key-care-human-action {display:flex!important;}.care-history .current,.care-history .next {display:list-item!important;}</style>', unsafe_allow_html=True)
            with header.container():
                st.error(str(exc))
            with SessionLocal() as session:
                unchanged = session.get(AgentGoal, UUID(str(goal_id)))
            with progress.container():
                stepper(unchanged)
        else:
            st.error(str(exc))


def stepper(goal):
    labels = ['报告接收', '系统分析', '责任分流', '专业确认', '行动建立', '完成']
    current = {'REPORT_RECEIVED': 0, 'ANALYZING': 1, 'WAITING_MANAGER_REVIEW': 3,
               'WAITING_DOCTOR_REVIEW': 3, 'WAITING_ACTION_APPROVAL': 4, 'CREATING_ACTIONS': 4,
               'COMPLETED': 5, 'ESCALATED': 2, 'FAILED': 2}.get(goal.current_stage, 1)
    pieces = []
    for index, label in enumerate(labels):
        skipped = False  # Professional confirmation includes the mandatory manager gate.
        status = '已跳过' if skipped else '已完成' if index < current or goal.status == 'COMPLETED' else '当前' if index == current else '待开始'
        if index == 1 and goal.status in {'ESCALATED','FAILED'} and not goal.context_json.get('structured'):
            status='需人工核对'
        mark = '—' if skipped else '✓' if status == '已完成' else '●' if status == '当前' else '○'
        pieces.append(f'<div role="listitem" class="flow-step {"active" if index == current else "done" if status == "已完成" else ""}"><b class="flow-dot">{mark}</b><span>{label}<br><small>{status}</small></span></div>')
    st.markdown('<div role="list" aria-label="体检后管理进度" class="v2-workflow">'+''.join(pieces)+'</div>', unsafe_allow_html=True)


def evidence(goal, *, doctor=False, show_findings=True):
    context = goal.context_json
    findings = context.get('findings', [])
    if show_findings:
        st.subheader('本次发现')
        st.caption(('本次资料已由健管核对入档。' if context.get('manager_confirmed') else '本次报告提取值需人工核对。')+'变化表示数值差异，不代表医学判断。')
        data_table(findings, [{'指标': f['label'], '本次': f"{f['value']:g} {f['unit']}",
        '年度基线': f"{f['baseline']:g} {f['unit']}" if f['baseline'] is not None else '尚无可比基线',
        '变化': f"{f['delta']:+g} {f['unit']}" if f['delta'] is not None else '—', '状态': '已核对' if context.get('manager_confirmed') else f['status']} for f in findings],
        key=f'care-findings-{goal.id}-{doctor}', selectable=False, empty='暂无可自动提取的指标，请人工查看原报告。')
    drawable = [f for f in findings if len({p['at'] for p in f['points']}) > 1][:2]
    if drawable:
        st.subheader('健康变化')
        for column, finding in zip(st.columns(len(drawable)), drawable):
            with column:
                st.markdown(f"**{finding['label']} · 本次 {finding['value']:g} {finding['unit']}**")
                series = HealthSeries(finding['code'], finding['label'], finding['unit'], tuple(
                    HealthPoint(datetime.fromisoformat(p['at']), Decimal(str(p['value'])), p['source'].replace('待健管核对', '已核对') if context.get('manager_confirmed') else p['source']) for p in finding['points']))
                refs = [SimpleNamespace(code=finding['code'], label=finding['label'], unit=finding['unit'], value=finding['baseline'])]
                render_metric_trend([series], key=f'care-chart-{goal.id}-{finding["code"]}-{doctor}', compact=True, baseline_metrics=refs, current_marker=True)
    with st.expander('系统整理结果与会员背景', expanded=False):
        st.write(context.get('summary', '请人工核对报告。'))
        member = context.get('member', {})
        st.markdown('**当前用药**')
        data_table(member.get('medications', []), [{'药物': m['name'], '剂量': m['dose']+' '+m['unit'], '频次': m['frequency']} for m in member.get('medications', [])], key=f'care-meds-{goal.id}-{doctor}', selectable=False, empty='暂无已确认用药资料。')
        for title, value in [('已记录健康问题', member.get('history')), ('过敏', member.get('allergies')), ('手术 / 住院', member.get('procedures')),
            ('个人病史', member.get('intake', {}).get('个人病史')), ('已知症状', member.get('intake', {}).get('专项症状评估'))]:
            st.markdown('**'+title+'**')
            if isinstance(value, list) and value:
                labels = {'title':'内容', 'description':'说明', 'name':'名称', 'occurred_at':'时间', 'status':'状态',
                          '疾病或问题':'疾病或问题', '症状':'症状', '原始回答':'原始回答', '名称':'名称', '过敏反应':'过敏反应'}
                from executive_health_ai.ui.status_dictionary import status_label
                st.dataframe([{labels[k]: status_label(v) if k == 'status' else str(v) for k, v in r.items() if k in labels} if isinstance(r, dict) else {'内容': str(r)} for r in value], hide_index=True, width='stretch')
            elif isinstance(value, str) and value:
                st.write(value)
            else:
                st.caption('暂无已确认记录，请与会员核实。')
        st.markdown('**最近健康数据**')
        recent = context.get('recent_health_data', [])[-10:]
        data_table(recent, [{'指标': r['label'], '数值': r['value'], '单位': r['unit'], '时间': r['at'][:10]} for r in recent], key=f'care-recent-{goal.id}-{doctor}', selectable=False)
        for row in context.get('report', {}).get('narrative', []):
            st.write(row['text']); st.caption(f"报告第 {row['page'] or '—'} 页")
        st.markdown('**开放管理事项**')
        data_table(context.get('management', {}).get('open_items', []),
            [{'事项': r['title'], '负责人': r['owner'], '日期': r['due']} for r in context.get('management', {}).get('open_items', [])],
            key=f'care-open-{goal.id}-{doctor}', selectable=False)
    st.subheader('依据')
    rows = [{'来源': '本次体检报告', '内容': context.get('report', {}).get('title', '原始体检报告'),
             '时间': context.get('report', {}).get('at', '')[:10], 'detail': '\n'.join(f['evidence'] for f in findings)}]
    if context.get('baseline'):
        rows.append({'来源': '年度健康基线', '内容': '已确认年度基线', '时间': str(context['baseline']['year']),
                     'detail': '使用当前年度已确认基线，保持原有基线不变。'})
    rows += [{'来源': '历史体检', '内容': r['title'], '时间': r['at'][:10], 'detail': r['title']} for r in context.get('history_reports', [])]
    rows += [{'来源': '已审核知识库', '内容': k['title']+' · '+(k.get('location') or '正文'), '时间': (k.get('retrieved_at') or '').split('T')[0] or '已审核版本',
              'detail': '\n'.join(str(k.get(x) or '') for x in ('title', 'scope', 'excerpt', 'source', 'version', 'location', 'source_url'))} for k in context.get('knowledge', [])]
    chosen = data_table(rows, [{k: r[k] for k in ('来源', '内容', '时间')} for r in rows], key=f'care-evidence-{goal.id}-{doctor}', auto_select=False)
    if chosen:
        with st.expander('依据详情', expanded=True):
            st.write(chosen['detail'])
    if not context.get('knowledge'):
        st.caption('暂无匹配的已审核知识依据')
    with SessionLocal() as session:
        report = session.get(Document, UUID(goal.source_id))
    if report and Path(report.storage_reference).is_file():
        st.download_button('查看原始报告', Path(report.storage_reference).read_bytes(), file_name=report.title,
                           key=f'care-report-{goal.id}-{doctor}')


def manager_detail(app, goal_id):
    with SessionLocal() as session:
        goal = session.get(AgentGoal, UUID(str(goal_id)))
        from executive_health_ai.services.member_archive import is_archived
        if goal and is_archived(session,goal.member_id):
            st.session_state.pop('care-detail',None)
            st.info('成员已归档，自动流程已停止；历史记录由管理员查阅。')
            return
    if goal and goal.goal_type == 'PROFILE_INTAKE':
        from executive_health_ai.ui.pages.manager.profile_intake import open_board
        open_board(app,goal,origin=st.session_state.get('care-origin','今日工作'));st.rerun()
        return
    if not goal or not flow.is_care_goal(goal):
        st.error('此报告事项不可用。'); return
    origin=st.session_state.get('care-origin','今日工作')
    if st.button('← 返回'+origin):
        st.session_state.pop('care-detail', None)
        st.session_state['today-work-grid-epoch'] = st.session_state.get('today-work-grid-epoch', 0)+1
        if origin=='会员360':
            app._open_member(goal.member_id)
        st.rerun()
    from executive_health_ai.ui.pages.manager.operations_board import render
    # A waiting board updates quietly every 30s; active processing is checked
    # every 5s. Data is always re-read from the same persisted goal.
    @st.fragment(run_every=5 if goal.status == 'RUNNING' else 30 if goal.status == 'WAITING_DOCTOR' else None)
    def live_board():
        with SessionLocal() as session:
            current = session.get(AgentGoal, UUID(str(goal_id)))
        if (current.status,current.current_stage) != (goal.status,goal.current_stage):
            # Rebuild the interval when a wait ends. Human edit forms must not
            # keep refreshing on the old doctor's waiting timer.
            st.rerun()
        render(app,current)
    live_board()


def _manager_action(app, goal, activity, live):
    context = goal.context_json
    if goal.status == 'COMPLETED':
        st.subheader('本次自动管理已完成')
        st.success('本次体检后管理已完成')
        from executive_health_ai.ui.pages.manager.care_activity import entry_text
        st.caption('入口：新体检报告 · '+entry_text(activity))
        st.markdown('**系统完成**')
        st.write('✓ 报告整理 · ✓ 健管确认')
        st.write('✓ '+('医生判断' if context.get('review_id') else '本次无需医生')+' · ✓ 后续行动建立')
        st.markdown('**最终产出**')
        refs = context['created']
        c.summary_strip([('管理事项', len(refs['tasks'])), ('复查计划', len(refs['rechecks'])), ('随访', len(refs['followups'])), ('服务申请', len(refs['services']))])
        st.caption('已回写 Member360 与年度管理；复查计划可在管理页查看，人工安排已进入今日工作。')
        node = context['next_node']
        st.info(f"下一节点：{node['due']} · {node['title']} · 负责人：{node['owner']}")
        if st.button('返回会员360', type='primary'):
            st.session_state.pop('care-detail', None); app._open_member(goal.member_id); st.rerun()
        if st.button('查看已创建事项'):
            st.session_state.pop('care-detail',None)
            st.session_state[f'workflow-mode-{goal.member_id}']='管理事项'
            app._open_member_management(goal.member_id);st.rerun()
    elif goal.current_stage == 'WAITING_DOCTOR_REVIEW' and goal.status != 'RUNNING':
        from executive_health_ai.models import DoctorReview
        with SessionLocal() as session:
            review = session.get(DoctorReview, UUID(context['review_id']))
        st.subheader('正在等待医生判断')
        st.info('当前无需健管操作。助手已准备医学问题和可用资料并提交医生。')
        st.info(f"责任医生：{review.doctor_name} · 提交时间：{ux.local_time(review.created_at).strftime('%Y-%m-%d %H:%M')}")
        st.caption('医生提交后系统会自动继续；需要您确认的后续行动会重新进入今日工作。')
    elif goal.status=='RUNNING':
        st.subheader(activity.headline)
        st.info('当前正在：'+activity.current)
        st.write('下一步：'+activity.next_action)
        st.caption(activity.after_confirmation)
    elif goal.current_stage == 'WAITING_ACTION_APPROVAL':
        st.subheader('现在需要你做')
        st.markdown('**现在轮到您：核对后续行动的负责人、日期与依据**')
        st.info(activity.after_confirmation)
        if context.get('doctor_result'):
            st.caption('医生意见：'+context['doctor_result']['judgement'][:160])
            with st.expander('查看完整医生意见'):
                st.write(context['doctor_result']['judgement']); st.write(context['doctor_result']['recommendation'])
        records = [{'行动': a['title'], '类型': KINDS[a['kind']], '时间': date.fromisoformat(a['due']),
                    '负责人': a['owner'], '依据': a['evidence']} for a in context['actions']]
        from executive_health_ai.models import ServiceCatalogItem
        with SessionLocal() as session:
            catalog = {r.name: r.code for r in session.scalars(select(ServiceCatalogItem).where(ServiceCatalogItem.status == 'ACTIVE'))}
        for record in records:
            record['服务项目'] = '不涉及'
        edited = st.data_editor(pd.DataFrame(records), num_rows='dynamic', hide_index=True, width='stretch',
            key=f'care-actions-{goal.id}', column_config={'类型': st.column_config.SelectboxColumn(options=list(KINDS.values()), required=True),
            '时间': st.column_config.DateColumn(required=True, min_value=date.today()), '负责人': st.column_config.TextColumn(required=True),
            '服务项目': st.column_config.SelectboxColumn(options=['不涉及', *catalog], help='仅服务行动需要选择')})
        if st.button('确认并创建后续安排', type='primary'):
            reverse = {v: k for k, v in KINDS.items()}
            actions = [{'title': r.get('行动'), 'kind': reverse.get(r.get('类型')), 'due': str(r.get('时间')),
                        'owner': r.get('负责人'), 'evidence': r.get('依据'), 'service_code': catalog.get(r.get('服务项目'))} for r in edited.to_dict('records')]
            command(goal.id, lambda s, g: flow.approve_actions(HealthOpsAgentSupervisor(), s, g, actions=actions, actor=g.owner, role='HEALTH_MANAGER'), activity='建立已确认的管理安排并核对下一节点', panel=live)
    elif goal.status == 'WAITING_MANAGER':
        st.subheader('现在需要你做')
        findings_count = len(context.get('findings', []))
        st.write(f'确认系统整理的 {findings_count} 项健康变化' if findings_count else '人工核对本次报告与处理路径')
        st.caption(activity.after_confirmation)
        from executive_health_ai.agent import care_routing
        with SessionLocal() as session:
            required_doctor=care_routing.evaluate(session,goal).route_type=='DOCTOR'
        if context.get('llm_status') == 'UNAVAILABLE':
            st.caption('自动整理暂不可用；已保留规则提取资料，可人工核对后继续。')
        with st.form(f'care-initial-{goal.id}'):
            if required_doctor:
                send=st.form_submit_button('确认并提交医生',type='primary')
                confirm=False
                st.caption('现有依据需要医学判断，请明确责任医生；提交后助手会等待医生返回。')
                doctor=st.text_input('责任医生',placeholder='填写本次负责判断的医生')
                question=st.text_area('需要医生判断的问题',value='本次指标变化是否需要进一步医学处理？',height=68)
                with st.expander('修改整理结果'):
                    summary=st.text_area('健管确认摘要',value=context.get('summary',''))
            else:
                confirm = st.form_submit_button('确认并继续', type='primary')
                with st.expander('修改整理结果 / 提交医生判断'):
                    summary = st.text_area('健管确认摘要', value=context.get('summary', ''))
                    doctor = st.text_input('责任医生', placeholder='填写本次负责判断的医生')
                    question = st.text_area('需要医生判断的问题', value='本次指标变化是否需要进一步医学处理？')
                    send = st.form_submit_button('提交医生判断')
        if send or confirm:
            command(goal.id, lambda s, g: flow.manager_review(HealthOpsAgentSupervisor(), s, g, actor=g.owner,
                role='HEALTH_MANAGER', summary=summary, doctor=doctor if send else None, question=question), panel=live)
        with st.expander('核对或修正原报告资料'):
            if st.button('打开报告核对'):
                app._open_report_review_from_worklist(goal.member_id, UUID(goal.source_id))
            refresh = st.button('刷新已修改资料')
        if refresh:
            command(goal.id, lambda s, g: flow.analyze(HealthOpsAgentSupervisor(), s, g), activity='重新读取报告、核对基线与历史资料并整理确认内容', panel=live, current_stage='ANALYZING')
    else:
        st.subheader('现在需要你做')
        st.warning(goal.next_action or '请人工核对报告资料。')
        if st.button('重新读取已补充资料', type='primary'):
            command(goal.id, lambda s, g: HealthOpsAgentSupervisor().resume_goal(s, g.id, actor=g.owner or '健康管理师'), activity='读取已补充资料并继续原流程', panel=live)
        if st.button('进入会员档案人工处理'):
            st.session_state.pop('care-detail', None); app._open_member(goal.member_id); st.rerun()


def doctor_detail(goal, *, read_only=False):
    from executive_health_ai.models import DoctorReview
    with SessionLocal() as session:
        review = session.get(DoctorReview, UUID(goal.context_json['review_id']))
    st.header(goal.context_json['member']['name']+' · 体检后医学复核')
    st.subheader('需要判断的问题')
    st.write(review.question_for_doctor)
    st.caption('责任医生：'+review.doctor_name+' · 来源：体检后健康管理')
    clinical, decision = st.columns([1.55, 1])
    with clinical:
        evidence(goal, doctor=True)
    with decision:
        if review.status == 'CONFIRMED':
            st.success('医学判断已提交，健康管理师将确认后续安排。'); st.write(review.opinion)
        elif not read_only:
            with st.form(f'care-doctor-{review.id}'):
                st.subheader('填写医学判断')
                judgement = st.text_area('医学判断', height=90)
                recommendation = st.text_area('建议', height=90)
                a, b = st.columns(2)
                recheck = a.radio('是否复查', ['不需要', '需要'], horizontal=True)
                title = b.text_input('复查项目')
                due = a.date_input('建议时间', value=date.today()+timedelta(days=90), min_value=date.today())
                follow = b.date_input('随访时间', value=date.today()+timedelta(days=30), min_value=date.today())
                with st.expander('其他说明'):
                    notes = st.text_area('补充说明')
                submit = st.form_submit_button('提交判断', type='primary')
            if submit:
                command(goal.id, lambda s, g: PostCheckupCareService().submit_review(s, g, actor=review.doctor_name, role='DOCTOR',
                    judgement=judgement, recommendation=recommendation, recheck=recheck=='需要', recheck_title=title,
                    suggested_date=due, followup_date=follow, notes=notes),
                    activity='保存医生判断，并将医生意见整理为后续行动', received='已收到本次提交的医生意见')


def member_summary(member_id,app=None):
    with SessionLocal() as session:
        goals = [g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id == member_id).order_by(AgentGoal.updated_at.desc(), AgentGoal.started_at.desc())) if flow.is_care_goal(g) or g.goal_type == "PROFILE_INTAKE"]
    st.subheader('自动跟进')
    if not goals:
        st.caption('当前没有自动流程记录。上传体检报告或导入健康资料后，将在这里显示实际处理进展。')
        st.write('最近完成：暂无记录')
        st.write('下一步：在医疗或健康档案中补充资料。')
        st.button('查看运行看板', key=f'member-no-progress-{member_id}', disabled=True,
                  help='尚无运行实例；查看入口不会创建新流程。')
        return
    goal = goals[0]
    if goal.goal_type == 'PROFILE_INTAKE':
        from executive_health_ai.ui.pages.manager.profile_intake import STATUS, stepper as profile_stepper, progress_steps
        st.markdown('**自动跟进 · 健康资料导入**')
        st.caption('开始：'+ux.when(goal.started_at))
        st.write('当前：'+STATUS.get(goal.status,'待处理'))
        profile_stepper(goal)
        completed = [label for label,done,_ in progress_steps(goal) if done]
        st.write('最近完成：'+(completed[-1] if completed else '尚无已完成步骤'))
        st.write('下一步：'+goal.next_action)
        if app:
            from executive_health_ai.ui.pages.manager.assistant import open_care
            st.button('处理资料与初评',key=f'member-profile-progress-{member_id}',on_click=open_care,args=(app,goal,'会员360'))
        return
    from executive_health_ai.ui.pages.manager import care_activity
    activity=care_activity.load(goal)
    st.markdown('**自动跟进 · 体检后健康管理**')
    st.caption('开始：'+care_activity.entry_text(activity))
    st.write('当前：'+activity.current)
    from executive_health_ai.services.care_board import project
    with SessionLocal() as session:
        board=project(session,goal)
    st.caption('当前责任：'+board.owner+' · '+board.route.reason_summary)
    stepper(goal)
    st.write('最近完成：'+(activity.done[-1].title if activity.done else '尚无已完成工作记录'))
    st.info('下一步：'+activity.next_action)
    if goal.status=='WAITING_DOCTOR':st.caption('医生提交后系统会自动继续。')
    if app:
        from executive_health_ai.ui.pages.manager.assistant import open_care
        st.button('查看运行看板',key=f'member-care-progress-{member_id}',on_click=open_care,args=(app,goal,'会员360'))
