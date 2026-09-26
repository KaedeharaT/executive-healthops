"""One business operations board, shared by Today, Member360 and admin."""
from html import escape

import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentPlanStep, AgentRunTrace
from executive_health_ai.services.care_board import project
from executive_health_ai.services.responsibility import LABELS, REASONS
from executive_health_ai.ui import components as c, experience as ux
from executive_health_ai.ui.presentation import data_table
from executive_health_ai.ui.status_dictionary import status_label
from executive_health_ai.ui.display import get_risk_display
from executive_health_ai.ui.pages.manager import care_activity


def styles():
    care_activity.styles()
    st.markdown('''<style>
    [class*="st-key-board-"] {border-color:#cfdfed!important;}
    .st-key-board-header {background:#f2f8fd;border-top:4px solid #2166a1!important;}
    body:has(.st-key-board-header) .v2-workflow {margin:10px 0!important;padding:10px 6px!important;min-height:70px!important;}
    .st-key-board-activity hr {margin:8px 0!important;}
    .board-current {background:#eaf3fc;border-left:4px solid #2166a1;padding:12px 16px;margin-bottom:12px;}
    .board-current strong {font-size:20px;color:#164b76;}
    .board-current p {margin:5px 0 0;color:#53687c;}
    .route-line {display:flex;gap:12px;align-items:center;padding:10px 12px;border-bottom:1px solid #e6edf4;}
    .route-line strong {min-width:110px;}.route-line span {font-size:13px;color:#64758a;}
    .route-line.chosen {background:#eaf3fc;border-left:4px solid #2875b3;}
    .route-line.chosen.manager {background:#e9f6f3;border-left-color:#237c73;}
    .route-line.chosen.doctor {background:#fff4e5;border-left-color:#b77522;}
    .route-line.chosen.escalate {background:#fff0ee;border-left-color:#ba4135;}
    .board-route-reason {margin-top:14px;color:#223d55;line-height:1.65;}
    .board-next {padding:9px 0;border-bottom:1px solid #e4edf5;color:#334d64;}
    .board-next b {display:inline-block;color:#22649b;margin-right:12px;}
    .board-risk-table {width:100%;table-layout:fixed;border-collapse:collapse;font-size:13px;}
    .board-risk-table th,.board-risk-table td {padding:8px 6px;border-bottom:1px solid #dde7f0;overflow-wrap:anywhere;vertical-align:top;text-align:left;}
    .board-risk-table th {color:#546b80;background:#f1f6fa;}
    .st-key-board-first,.st-key-board-history,.st-key-board-clinical,.st-key-board-support,.st-key-board-exit {margin-top:24px;}
    </style>''', unsafe_allow_html=True)


def routing(board, goal, activity):
    st.subheader('当前责任分流')
    completed = {r.route_type for r in board.route_history}
    descriptions = {'AUTO':'资料整理、比较与已确认安排', 'MANAGER':'管理重点、沟通与执行安排',
                    'DOCTOR':'医学意义、检查、用药与治疗判断', 'ESCALATE':'安全异常，暂停普通自动流程'}
    lines = []
    for kind, label in LABELS.items():
        selected = kind == board.route.route_type
        state = '● 当前责任' if selected else '✓ 已经过' if kind in completed else '未触发' if kind == 'ESCALATE' else '尚未进入'
        if not selected and kind == 'AUTO' and activity.done:
            state = '✓ 已完成资料整理' if goal.context_json.get('structured') else '已读取可用资料，尚待核实'
        if not selected and kind == 'MANAGER':
            state = '✓ 已确认报告' if goal.context_json.get('manager_confirmed') else '待健管核对并提交'
        if not selected and kind == 'DOCTOR':
            state = ('✓ 已完成医学判断' if board.doctor_opinion else
                     '已关联医生复核' if goal.context_json.get('review_id') else
                     '本次无需医生' if goal.status=='COMPLETED' else '按医学需要进入')
        lines.append(f'<div class="route-line {"chosen" if selected else ""} {kind.lower()}"><strong>{escape(label)}</strong><span>{state}<br>{descriptions[kind]}</span></div>')
    st.markdown(''.join(lines), unsafe_allow_html=True)
    title = {'AUTO':'为什么系统可以继续', 'MANAGER':'为什么轮到健管', 'DOCTOR':'为什么交给医生', 'ESCALATE':'为什么需要优先处理'}[board.route.route_type]
    st.markdown(f'<div class="board-route-reason"><b>{title}</b><br>{escape(board.route.reason_summary)}</div>', unsafe_allow_html=True)
    st.caption('现在负责：'+board.owner)
    if board.route.route_type == 'DOCTOR' and not board.owner.startswith('医生 '):
        st.caption('医学责任属于医生；当前由健管核对资料并明确责任医生。')
    sources = {'document':'本次体检报告', 'baseline':'年度健康基线', 'doctor_review':'医生复核记录',
               'risk_event':'正式风险记录', 'report_candidate':'本次报告提取资料'}
    names = list(dict.fromkeys(sources.get(ref.split(':')[0], '业务依据') for ref in board.route.evidence_refs))
    st.caption('分流依据：'+' · '.join(names))


def human_history(board):
    st.subheader('人工参与')
    lines = []
    for event in board.humans:
        stamp = ux.local_time(event.at).strftime('%m/%d %H:%M') if event.at else ''
        lines.append(f'<li><span class="mark">✓</span><time>{escape(stamp)}</time>{escape(event.title)} · {escape(event.owner)}</li>')
    if not lines:
        lines.append('<li>尚无已提交的人工确认。</li>')
    st.markdown('<ol class="care-history" aria-label="人工参与记录">'+''.join(lines)+'</ol>', unsafe_allow_html=True)
    st.divider()
    st.subheader('接下来会发生什么')
    for index, step in enumerate(board.next_steps, 1):
        st.markdown(f'<div class="board-next"><b>{index:02d}</b>{escape(step)}</div>', unsafe_allow_html=True)


def clinical_boundary(board):
    st.subheader('正式风险规则')
    st.caption('来自现有确定性风险规则；与系统整理的数值变化分开记录。')
    if board.risks:
        records = [{k: get_risk_display(v) if k=='等级' else status_label(v,context='risk_event') if k=='状态' else v
                    for k,v in row.items() if k != 'new_for_report'} for row in board.risks]
        headers=('规则','等级','触发原因','状态','处理责任')
        cells=''.join('<tr>'+''.join('<td>'+escape(str(row[k])[:65])+('…' if len(str(row[k]))>65 else '')+'</td>' for k in headers)+'</tr>' for row in records)
        st.markdown('<table class="board-risk-table" aria-label="正式风险规则"><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+cells+'</tbody></table>',unsafe_allow_html=True)
        if any(len(str(r[k]))>65 for r in records for k in headers):
            with st.expander('查看完整规则依据'):
                for row in records:
                    st.markdown('**'+row['规则']+'**')
                    st.write(row['触发原因'])
        if not any(r['new_for_report'] for r in board.risks):
            st.caption('显示会员当前已有的正式风险记录，未认定为本报告新触发的风险。')
    else:
        st.info('本次没有新的正式风险规则触发。')
    st.divider()
    st.markdown('**医生判断**')
    if board.doctor_opinion:
        st.write(board.doctor_opinion[:120])
        if len(board.doctor_opinion) > 120:
            with st.expander('完整医学判断'):
                st.write(board.doctor_opinion)
    elif board.route.route_type == 'DOCTOR':
        st.write('等待责任医生提交医学判断。')
    else:
        st.caption('暂无本次医生判断。系统整理结果不构成诊断或治疗决定。')


def technical(goal):
    with st.expander('技术详情', expanded=False):
        st.caption('仅管理员可见 · 不展示提示词、隐藏推理或原始结果载荷')
        st.write('Goal：'+goal.title)
        st.write('Event：REPORT_UPLOADED · State：'+goal.current_stage)
        with SessionLocal() as session:
            steps = list(session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id == goal.current_plan_id).order_by(AgentPlanStep.step_order)))
            traces = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id == goal.id).order_by(AgentRunTrace.started_at)))
        st.dataframe([{'Step':s.step_type,'State':s.status,'Approval':s.approval_role or '—',
            'Wait':s.wait_event_type or '—','Retry':s.retry_count} for s in steps], hide_index=True, width='stretch')
        st.dataframe([{'时间':ux.local_time(t.started_at), 'Tool':t.tool_name or '—', 'Event / Resume':t.action,
            'State':t.status, 'Error':'有异常，请核对业务资料' if t.error_summary else '—'} for t in traces], hide_index=True, width='stretch')
        routes = [t.metadata_json['responsibility'] for t in traces if t.action == 'responsibility_routed']
        st.dataframe([{'Route':r['route_type'], 'Reason':r['reason_summary'], 'Rules':len(r['rule_refs']),
            'Evidence':len(r['evidence_refs']), 'Confirmed by':r['confirmed_by'] or '系统规则', 'Time':r['created_at']} for r in routes], hide_index=True, width='stretch')


def render(app, goal, *, admin=False):
    from executive_health_ai.ui.pages.manager.post_checkup import stepper, _manager_action, evidence
    styles()
    activity = care_activity.load(goal)
    with SessionLocal() as session:
        board = project(session, goal)
    ctx = goal.context_json
    st.header('健康管理助手 · 运行看板')
    with st.container(border=True, key='board-header'):
        st.subheader(ctx.get('member', {}).get('name', '会员')+' · 体检后健康管理')
        st.caption('开始原因：'+care_activity.entry_text(activity))
        hours, minutes = divmod(board.elapsed_minutes, 60)
        live = st.empty()
        with live.container():
            c.summary_strip([('责任健管',goal.owner or '待确认'),('现在轮到',board.owner),
                ('运行时长（含等待）',f'{hours} 小时 {minutes} 分钟'),('当前状态',activity.current)])
            st.markdown(f'<div class="board-current"><strong>{escape(activity.headline)}</strong><p>当前：{escape(activity.current)}</p></div>', unsafe_allow_html=True)
    progress = st.empty()
    with progress.container():
        stepper(goal)
    action_approval = goal.current_stage == 'WAITING_ACTION_APPROVAL' and not admin
    if action_approval:
        with st.container(border=True, key='care-human-action'):
            _manager_action(app,goal,activity,(live,progress))
    with st.container(key='board-first'):
        left, right = st.columns([1.35, 1], gap='large')
        with right, st.container(border=True, key='board-routing'):
            routing(board,goal,activity)
        with left, st.container(border=True, key='board-activity'):
            st.subheader('助手现在在做什么')
            st.caption('输入：本次报告、已有健康资料与年度基线 → 产出：已确认的后续安排' if goal.status == 'COMPLETED'
                else '输入：本次报告、已有健康资料与年度基线 → 产出：待核对摘要与行动草稿')
            if goal.status == 'COMPLETED':
                st.markdown('**已建立的后续安排**')
                refs=ctx.get('created',{})
                c.summary_strip([(label,len(refs.get(key,[]))) for label,key in [('管理事项','tasks'),('复查','rechecks'),('随访','followups'),('服务','services')]])
                st.info('下一节点：'+activity.next_action)
                st.caption('报告已转成实际安排，后续执行进入会员360与今日工作。')
            elif action_approval:
                st.write(activity.next_action)
                st.caption(activity.after_confirmation)
            else:
                st.divider()
                if admin:
                    st.write('业务下一步：'+activity.next_action)
                    st.caption('人工确认在对应健管或医生工作台完成。')
                else:
                    with st.container(key='care-human-action'):
                        _manager_action(app, goal, activity, (live, progress))
    with st.container(key='board-history'):
        left, right = st.columns([1.35,1], gap='large')
        with left, st.container(border=True, key='board-timeline'):
            care_activity.timeline(activity)
        with right, st.container(border=True, key='board-humans'):
            human_history(board)
    with st.container(key='board-clinical'):
        left, right = st.columns([1.35,1], gap='large')
        with left, st.container(border=True, key='board-findings'):
            st.subheader('系统发现')
            st.caption('报告整理与数值比较，待人工核对；不是诊断或正式风险分级。')
            st.caption('责任路径针对整份报告，不将单项数值变化解释为医学结论。')
            data_table(board.findings, list(board.findings), key=f'board-findings-{goal.id}',selectable=False,
                       empty='暂无可可靠整理的指标，请人工查看报告。')
        with right, st.container(border=True, key='board-risk'):
            clinical_boundary(board)
    with st.container(border=True, key='board-support'):
        st.subheader('智能辅助')
        names = {w.title for w in activity.done}
        c.summary_strip([('报告整理','已完成' if ctx.get('structured') else '需人工核对'),
            ('历史比较','已核对可用资料' if any('历史' in n for n in names) else '尚未完成'),
            ('已审核知识',f"{len(ctx.get('knowledge',[]))} 条"),
            ('医生资料','已准备' if ctx.get('review_id') else '需要时准备')])
        evidence(goal, show_findings=False)
    with st.container(border=True, key='board-exit'):
        if goal.status == 'COMPLETED' and not admin:
            _manager_action(app,goal,activity,(live,progress))
        else:
            st.subheader('最终产出' if goal.status == 'COMPLETED' else '本流程的业务出口')
            if goal.status == 'COMPLETED':
                refs=ctx.get('created',{})
                c.summary_strip([(label,len(refs.get(key,[]))) for label,key in [('管理事项','tasks'),('复查计划','rechecks'),('随访','followups'),('服务','services')]])
                st.write('下一节点：'+activity.next_action)
            else:
                st.write('管理事项 · 复查计划（有医生建议时） · 随访 · 服务安排（如需要）')
                st.caption('人工确认、负责人、日期和下一节点全部明确，并正式建立安排后，本流程才会完成。')
        if board.route_history:
            path=[]
            for r in board.route_history:
                if not path or path[-1] != LABELS[r.route_type]:path.append(LABELS[r.route_type])
            st.caption('已记录责任路径：'+' → '.join(path))
    if admin:
        technical(goal)
