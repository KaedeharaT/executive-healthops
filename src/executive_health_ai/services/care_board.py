"""Read-only business projection for the single post-checkup operations board."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from executive_health_ai.agent import care_routing
from executive_health_ai.models import AgentRunTrace, AgentApprovalRequest, DoctorReview, RiskRule
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.responsibility import LABELS, ResponsibilityRoute


@dataclass(frozen=True)
class HumanEvent:
    title: str
    owner: str
    at: datetime | None


@dataclass(frozen=True)
class CareBoard:
    route: ResponsibilityRoute
    owner: str
    findings: tuple[dict, ...]
    risks: tuple[dict, ...]
    humans: tuple[HumanEvent, ...]
    route_history: tuple[ResponsibilityRoute, ...]
    doctor_opinion: str | None
    elapsed_minutes: int
    next_steps: tuple[str, ...]


def project(session, goal):
    ctx = goal.context_json or {}
    decision = care_routing.evaluate(session, goal)
    risks, review = care_routing.facts(session, goal)
    owner = ('医生 '+review.doctor_name if goal.status == 'WAITING_DOCTOR' and review else
             '健康管理助手' if goal.status in {'RUNNING', 'PROCESSING', 'COMPLETED'} and decision.route_type != 'ESCALATE' else
             (goal.takeover_by or goal.owner or '待指派健康管理师'))
    rows = []
    for risk in risks:
        rule = session.get(RiskRule, risk.risk_rule_id)
        rows.append({'规则': rule.name if rule else '已记录规则', '等级': risk.risk_level,
            '触发原因': risk.summary, '状态': risk.status,
            '处理责任': '优先人工处理' if risk.requires_emergency_action else '医生判断' if risk.requires_doctor_review or risk.risk_level == 'RED' else '健管确认',
            'new_for_report': str(risk.evidence_json.get('document_id', '')) == goal.source_id})
    findings = []
    # No per-indicator medical route is fabricated. If no source-linked rule
    # exists, the responsibility is explicitly for the entire report.
    for f in ctx.get('findings', []):
        findings.append({'发现': f['label'], '本次': f"{f['value']:g} {f['unit']}",
            '基线 / 历史': f"{f['baseline']:g} {f['unit']}" if f.get('baseline') is not None else '尚无可比基线',
            '变化': f"{f['delta']:+g} {f['unit']}" if f.get('delta') is not None else '—',
            '责任路径': LABELS[decision.route_type],
            '核对状态': '已核对' if ctx.get('manager_confirmed') else f.get('status','待核对')})
    humans = []
    for approval in session.scalars(select(AgentApprovalRequest).where(
            AgentApprovalRequest.goal_id == goal.id, AgentApprovalRequest.status == 'APPROVED').order_by(AgentApprovalRequest.decided_at)):
        humans.append(HumanEvent('确认报告整理' if approval.approval_type == 'WAITING_MANAGER_REVIEW' else '确认后续行动',
                                 approval.decided_by or '健康管理师', approval.decided_at))
    if review:
        humans.append(HumanEvent('提交医学问题与资料', ctx.get('manager') or goal.owner or '健康管理师', review.created_at))
        if review.status == 'CONFIRMED':
            humans.append(HumanEvent('完成医学判断', review.doctor_name, review.reviewed_at))
    traces = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id == goal.id).order_by(AgentRunTrace.started_at)))
    history = []
    for t in traces:
        if t.action == 'resumed_after_doctor':
            humans.append(HumanEvent('收到医生意见，自动继续原流程', '健康管理助手', t.started_at))
        if t.action == 'responsibility_routed':
            data = dict(t.metadata_json['responsibility'])
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            history.append(ResponsibilityRoute(**data))
    humans.sort(key=lambda h: h.at.timestamp() if h.at else 0)
    if decision.route_type == 'ESCALATE':
        next_steps = ('责任人核对升级原因与关键资料', '处理原有安全事件或更正资料', '人工确认安全条件解除后继续原流程')
    elif goal.status == 'COMPLETED':
        next_steps = ('后续安排已进入会员360与今日工作', '按下一节点执行管理安排')
    elif goal.status == 'WAITING_DOCTOR':
        next_steps = ('责任医生提交医学判断', '助手自动继续，整理医生建议', '后续行动草稿进入健管今日工作', '健管确认后建立正式安排')
    elif goal.current_stage == 'WAITING_ACTION_APPROVAL':
        next_steps = ('健管确认行动、日期与负责人', '助手建立管理事项及相关复查、随访、服务', '记录结果并明确下一节点')
    else:
        next_steps = ('健管核对报告整理与管理重点', '需要医学判断时交给责任医生', '助手整理行动草稿，健管确认后建立安排')
    end = goal.completed_at or utc_now()
    minutes = max(0, int((end-goal.started_at).total_seconds()//60)) if goal.started_at else 0
    return CareBoard(decision, owner, tuple(findings), tuple(rows), tuple(humans), tuple(history),
        review.opinion if review and review.status == 'CONFIRMED' else None, minutes, next_steps)
