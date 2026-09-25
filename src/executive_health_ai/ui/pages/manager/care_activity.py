"""Read-only business presentation of the existing care goal and audit records."""
from dataclasses import dataclass
from datetime import datetime
from html import escape
from uuid import UUID

import streamlit as st
from sqlalchemy import select

from executive_health_ai.database import SessionLocal
from executive_health_ai.models import AgentEvent, AgentRunTrace, DoctorReview
from executive_health_ai.ui import experience as ux


@dataclass(frozen=True)
class WorkDone:
    title: str
    at: datetime | None = None


@dataclass(frozen=True)
class CareActivity:
    started_at: datetime | None
    current: str
    headline: str
    next_action: str
    after_confirmation: str
    done: tuple[WorkDone, ...]


def project(goal, traces=(), entry=None, review=None):
    """Only successful recorded actions become checkmarks; never parse raw output."""
    ctx = goal.context_json or {}
    done = []
    events = sorted(traces, key=lambda t: t.started_at)
    received = next((t for t in events if t.action == 'report_received'), None)
    started = entry.occurred_at if entry else received.started_at if received else goal.started_at
    if entry or received:
        done.append(WorkDone('收到本次体检报告，自动启动健康管理', started))
    tools = {t.tool_name: t for t in events if t.action == 'tool_completed' and t.status == 'COMPLETED'}

    def recorded(name, title):
        if record := tools.get(name):
            done.append(WorkDone(title, record.completed_at or record.started_at))

    recorded('get_report', '读取体检报告')
    recorded('get_baseline', '读取年度健康基线' if ctx.get('baseline') else '核对年度基线：尚无已确认资料')
    recorded('get_member_context', '整理会员健康资料与既往记录')
    comparable = any(f.get('baseline') is not None or len(f.get('points', [])) > 1 for f in ctx.get('findings', []))
    recorded('get_health_history', '比较本次指标与已有基线、历史变化' if comparable else '核对历史资料：暂无可比较记录')
    if any(t.action == 'knowledge_unavailable' for t in events) and not ctx.get('knowledge'):
        done.append(WorkDone('已检查知识服务：暂不可用，未生成替代依据'))
    else:
        recorded('retrieve_knowledge', '整理已审核知识依据' if ctx.get('knowledge') else '已查询知识库：暂无匹配的已审核依据')
    summary = next((t for t in reversed(events) if t.action == 'summary_drafted' and t.status in {'AVAILABLE', 'UNAVAILABLE'}), None)
    if summary:
        done.append(WorkDone(f"整理 {len(ctx.get('findings', []))} 项待确认的健康信息", summary.completed_at or summary.started_at))
    recorded('confirm_report_preparation', '已收到健管确认，核对报告资料入档')
    if 'create_doctor_review' in tools:
        record = tools['create_doctor_review']
        done.append(WorkDone('整理医学问题、指标及可用报告依据', record.completed_at or record.started_at))
        if any(len(f.get('points', [])) > 1 for f in ctx.get('findings', [])):
            done.append(WorkDone('准备有历史数据的健康趋势供医生查看', record.completed_at or record.started_at))
        recorded('create_doctor_review', '已提交责任医生判断')
    if review and review.status == 'CONFIRMED':
        done.append(WorkDone('已收到医生判断，原流程自动继续', review.reviewed_at))
    resumed = next((t for t in reversed(events) if t.action == 'resumed_after_doctor'), None)
    if ctx.get('actions') and (resumed or ctx.get('manager_confirmed')):
        done.append(WorkDone(f"整理 {len(ctx['actions'])} 项后续行动草稿，供健管核对", resumed.started_at if resumed else None))
    if ctx.get('actions_confirmed'):
        recorded('create_care_arrangements', '按健管确认正式建立后续安排并写入管理日志')
    if goal.status == 'COMPLETED':
        recorded('complete_agent_goal', '核对行动负责人、日期与下一节点，完成本次自动管理')

    stage, state = goal.current_stage, goal.status
    if state == 'COMPLETED':
        current, headline = '本次管理已完成', '健康管理助手已完成本次工作'
        node = ctx.get('next_node') or {}
        next_action = ' · '.join(str(node.get(k) or '') for k in ('due', 'title', 'owner')).strip(' ·') or '在会员360查看后续安排'
        after = '后续安排已进入会员管理；需要人工处理时会出现在今日工作。'
    elif state == 'WAITING_DOCTOR':
        current, headline = '等待医生判断', '健康管理助手正在等待医生判断'
        next_action, after = '医生提交后自动继续', '系统会整理医生意见为行动草稿，再请您确认安排。'
    elif state == 'RUNNING':
        headline = '健康管理助手继续工作' if ctx.get('doctor_result') else '健康管理助手正在工作'
        current = '正在建立正式后续安排' if stage == 'CREATING_ACTIONS' else '正在将医生意见整理为后续行动' if ctx.get('doctor_result') else '正在整理报告、健康资料与基线比较'
        next_action, after = '整理完成后，请健管确认安排' if ctx.get('doctor_result') else '准备健管确认内容', '当前无需操作；完成当前工作后自动进入下一步。'
    elif state == 'WAITING_MANAGER':
        current, headline = '等待您的确认', '健康管理助手已完成当前阶段'
        action_gate = stage == 'WAITING_ACTION_APPROVAL'
        next_action = f"确认 {len(ctx.get('actions', []))} 项后续安排" if action_gate else f"确认 {len(ctx.get('findings', []))} 项健康变化"
        after = '确认后系统会自动建立安排、写入管理日志并明确下一节点。' if action_gate else '确认后系统会自动继续：需要医学判断时提交医生；无需医生时整理后续行动草稿。'
    else:
        current, headline = '需要您补充资料或人工核对', '健康管理助手需要人工协助'
        next_action, after = '核对报告及会员资料', '补齐资料后继续原流程；未完成的工作不会标记为完成。'
    return CareActivity(started, current, headline, next_action, after, tuple(done))


def load(goal):
    with SessionLocal() as session:
        traces = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id == goal.id).order_by(AgentRunTrace.started_at)))
        entry = session.scalar(select(AgentEvent).where(AgentEvent.member_id == goal.member_id,
            AgentEvent.source_id == goal.source_id, AgentEvent.source_type == 'document',
            AgentEvent.event_type == 'REPORT_UPLOADED').order_by(AgentEvent.occurred_at))
        review = session.get(DoctorReview, UUID(goal.context_json['review_id'])) if goal.context_json.get('review_id') else None
    return project(goal, traces, entry, review)


def entry_text(activity):
    return (ux.local_time(activity.started_at).strftime('%Y-%m-%d %H:%M')+' · ' if activity.started_at else '')+'收到新的体检报告'


def styles():
    st.markdown('''<style>
    div[class*="st-key-assistant-card-"] {border-left:4px solid #1762a8;background:#f5faff;padding:16px!important;}
    .care-history {margin:8px 0;padding:0;list-style:none;border-left:2px solid #c4d9ea;}
    .care-history li {position:relative;padding:5px 8px 5px 22px;line-height:1.5;font-size:14px;}
    .care-history .mark {position:absolute;left:-9px;background:#f5faff;color:#1762a8;font-weight:700;}
    .care-history time {display:inline-block;color:#64768c;font-size:12px;margin-right:8px;}
    .care-history .current {background:#e6f1fc;color:#114f87;font-weight:600;}
    .care-history .next {color:#64768c;}
    </style>''', unsafe_allow_html=True)


def timeline(activity):
    st.subheader('健康管理助手已替您完成')
    lines = []
    for work in activity.done:
        stamp = ux.local_time(work.at).strftime('%m/%d %H:%M') if work.at else ''
        lines.append(f'<li><span class="mark">✓</span><time>{escape(stamp)}</time>{escape(work.title)}</li>')
    if not lines:
        lines.append('<li>尚无已完成工作记录，不预先标记完成。</li>')
    lines.append(f'<li class="current"><span class="mark">●</span>当前：{escape(activity.current)}</li>')
    lines.append(f'<li class="next"><span class="mark">○</span>下一步：{escape(activity.next_action)}</li>')
    st.markdown('<ol class="care-history" aria-label="助手工作记录">'+''.join(lines)+'</ol>', unsafe_allow_html=True)
