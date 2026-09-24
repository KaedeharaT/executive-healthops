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


def command(goal_id, callback):
    try:
        with SessionLocal() as session:
            callback(session, session.get(AgentGoal, UUID(str(goal_id))))
            session.commit()
        st.rerun()
    except (ValueError, PermissionError) as exc:
        st.error(str(exc))


def stepper(goal):
    labels = ['报告接收', '系统整理', '健管确认', '医生复核', '行动确认', '完成']
    current = {'REPORT_RECEIVED': 0, 'ANALYZING': 1, 'WAITING_MANAGER_REVIEW': 2,
               'WAITING_DOCTOR_REVIEW': 3, 'WAITING_ACTION_APPROVAL': 4, 'CREATING_ACTIONS': 4,
               'COMPLETED': 5, 'ESCALATED': 1, 'FAILED': 1}.get(goal.current_stage, 1)
    pieces = []
    for index, label in enumerate(labels):
        skipped = index == 3 and current > 3 and not goal.context_json.get('review_id')
        status = '已跳过' if skipped else '已完成' if index < current or goal.status == 'COMPLETED' else '当前' if index == current else '待开始'
        mark = '—' if skipped else '✓' if status == '已完成' else '●' if status == '当前' else '○'
        pieces.append(f'<div role="listitem" class="flow-step {"active" if index == current else ""}"><b class="flow-dot">{mark}</b><span>{label}<br><small>{status}</small></span></div>')
    st.markdown('<div role="list" aria-label="体检后管理进度" class="v2-workflow">'+''.join(pieces)+'</div>', unsafe_allow_html=True)


def evidence(goal, *, doctor=False):
    context = goal.context_json
    findings = context.get('findings', [])
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
    if not goal or not flow.is_care_goal(goal):
        st.error('此报告事项不可用。'); return
    if st.button('← 返回今日工作'):
        st.session_state.pop('care-detail', None)
        st.session_state['today-work-grid-epoch'] = st.session_state.get('today-work-grid-epoch', 0)+1
        st.rerun()
    context = goal.context_json
    st.header(context.get('member', {}).get('name', '会员')+' · 体检后健康管理')
    c.summary_strip([('责任健管', goal.owner or '待确认'), ('当前状态', flow.LABELS.get(goal.current_stage, '需人工处理')),
                     ('本次报告', context.get('report', {}).get('at', '')[:10])])
    stepper(goal)
    if goal.status == 'COMPLETED':
        st.success('本次体检后管理已完成')
        refs = context['created']
        c.summary_strip([('管理事项', len(refs['tasks'])), ('复查计划', len(refs['rechecks'])), ('随访', len(refs['followups'])), ('服务申请', len(refs['services']))])
        node = context['next_node']
        st.info(f"下一节点：{node['due']} · {node['title']} · 负责人：{node['owner']}")
        if st.button('返回会员360', type='primary'):
            st.session_state.pop('care-detail', None); app._open_member(goal.member_id); st.rerun()
    elif goal.current_stage == 'WAITING_DOCTOR_REVIEW':
        from executive_health_ai.models import DoctorReview
        with SessionLocal() as session:
            review = session.get(DoctorReview, UUID(context['review_id']))
        st.subheader('等待医生判断')
        st.info(f'责任医生：{review.doctor_name} · 提交时间：{ux.local_time(review.created_at)}')
        st.caption('报告、基线、趋势和会员背景已随本次问题交给医生，提交后会自动返回此处。')
    elif goal.current_stage == 'WAITING_ACTION_APPROVAL':
        st.subheader('需要您处理')
        st.write('请核对负责人和日期，确认后一次建立后续安排。')
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
            command(goal.id, lambda s, g: flow.approve_actions(HealthOpsAgentSupervisor(), s, g, actions=actions, actor=g.owner, role='HEALTH_MANAGER'))
    elif goal.status == 'WAITING_MANAGER':
        st.subheader('需要您处理')
        st.write('请核对本次指标及处理路径。确认后，提取资料按现有规则入档；需要医学判断时提交责任医生。')
        if context.get('llm_status') == 'UNAVAILABLE':
            st.caption('自动整理暂不可用；已保留规则提取资料，可人工核对后继续。')
        with st.form(f'care-initial-{goal.id}'):
            with st.expander('修改整理结果 / 提交医生判断'):
                summary = st.text_area('健管确认摘要', value=context.get('summary', ''))
                doctor = st.text_input('责任医生', placeholder='填写本次负责判断的医生')
                question = st.text_area('需要医生判断的问题', value='本次指标变化是否需要进一步医学处理？')
                send = st.form_submit_button('提交医生判断')
            confirm = st.form_submit_button('确认并继续', type='primary')
        if send or confirm:
            command(goal.id, lambda s, g: flow.manager_review(HealthOpsAgentSupervisor(), s, g, actor=g.owner,
                role='HEALTH_MANAGER', summary=summary, doctor=doctor if send else None, question=question))
        with st.expander('核对或修正原报告资料'):
            if st.button('打开报告核对'):
                app._open_report_review_from_worklist(goal.member_id, UUID(goal.source_id))
            if st.button('刷新已修改资料'):
                command(goal.id, lambda s, g: flow.analyze(HealthOpsAgentSupervisor(), s, g))
    else:
        st.subheader('需要您处理')
        st.warning(goal.next_action or '请人工核对报告资料。')
        if st.button('重新读取已补充资料', type='primary'):
            command(goal.id, lambda s, g: HealthOpsAgentSupervisor().resume_goal(s, g.id, actor=g.owner or '健康管理师'))
        if st.button('进入会员档案人工处理'):
            st.session_state.pop('care-detail', None); app._open_member(goal.member_id); st.rerun()
    evidence(goal)


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
                    suggested_date=due, followup_date=follow, notes=notes))


def member_summary(member_id):
    with SessionLocal() as session:
        goals = [g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id == member_id).order_by(AgentGoal.started_at.desc())) if flow.is_care_goal(g)]
    if not goals:
        return
    goal = goals[0]
    st.markdown('**当前自动跟进**')
    node = goal.context_json.get('next_node')
    c.summary_strip([('体检后管理', flow.LABELS.get(goal.current_stage, '需人工处理')),
        ('下一节点', node['due']+' · '+node['title'] if node else goal.next_action),
        ('负责人', node['owner'] if node else goal.owner or '待确认')])
