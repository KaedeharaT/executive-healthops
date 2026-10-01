"""Small read-only oversight projections over existing records, no dashboard state."""
from datetime import timedelta
from sqlalchemy import select
from executive_health_ai.models import AgentGoal, AgentRunTrace, MemberAgent, Patient, RiskEvent
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.autonomy import current_risk, MODES


def member(session, member_id):
    risk = current_risk(session, member_id)
    if risk is None:
        return {'level': None, 'label': '按当前计划管理', 'next_action': '', 'owner': '', 'risk_id': None}
    goals = list(session.scalars(select(AgentGoal).where(AgentGoal.member_id == member_id,
        AgentGoal.goal_type == 'DAILY_CARE').order_by(AgentGoal.started_at.desc())))
    goal = next((g for g in goals if g.context_json.get('risk_event_id') == str(risk.id)), None)
    from executive_health_ai.services.risk_autonomy import responsibility_for
    role = responsibility_for(session, risk).route_type
    return {'level': risk.risk_level, 'label': {'GREEN': '正常自动管理', 'YELLOW': '需关注', 'RED': '优先处理'}[risk.risk_level],
        'next_action': goal.next_action if goal else risk.summary,
        'owner': '医生' if goal and goal.status == 'WAITING_DOCTOR' else (goal.owner if goal else risk.acknowledged_by) or '责任健管',
        'status': goal.status if goal else risk.status, 'responsibility': role, 'risk_id': risk.id,
        'reason': risk.summary}


def oversight(session, now=None):
    now = now or utc_now()
    agents = list(session.scalars(select(MemberAgent).join(Patient, Patient.id == MemberAgent.member_id)
        .where(Patient.archived_at.is_(None))))
    risks = {a.member_id: current_risk(session, a.member_id) for a in agents}
    traces = list(session.scalars(select(AgentRunTrace).where(AgentRunTrace.started_at >= now - timedelta(hours=24))))
    decisions = [t for t in traces if t.action == 'autonomy_decision']
    return {'managed': len(agents),
        'no_human': sum(a.status in {'IDLE', 'RUNNING', 'WAITING_TIME'} and
            (risks[a.member_id] is None or risks[a.member_id].risk_level == 'GREEN') for a in agents),
        'attention': sum(bool(r and r.risk_level == 'YELLOW') for r in risks.values()),
        'urgent': sum(bool(r and r.risk_level == 'RED') for r in risks.values()),
        'automatic_completed': sum(t.action == 'goal_completed' for t in traces),
        'created_followups': sum(t.action == 'tool_execution' and t.status == 'COMPLETED' and
            t.tool_name in {'create_followup', 'create_recheck', 'create_followup_task'} for t in traces),
        'yellow_handoffs': len({t.goal_id for t in traces if t.action == 'wait' and t.metadata_json.get('risk_level') == 'YELLOW' and t.metadata_json.get('state') == 'WAITING_MANAGER'}),
        'red_handoffs': len({t.goal_id for t in traces if t.action == 'autonomy_prepared' and t.metadata_json.get('risk_level') == 'RED'}),
        'failed': sum(t.action == 'human_escalation' for t in traces)}
