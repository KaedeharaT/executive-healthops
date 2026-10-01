"""Operational failure handoff, using the existing task and human work queue."""
from sqlalchemy import select
from executive_health_ai.models import Task
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.management_workflow import task
from executive_health_ai.services import care_runtime


def attention(session, goal, reason):
    from uuid import UUID
    from executive_health_ai.models import RiskEvent
    risk = session.get(RiskEvent, UUID(goal.context_json['risk_event_id'])) if goal.context_json.get('risk_event_id') else None
    if risk and risk.risk_level in {'YELLOW', 'RED'} and risk.status not in {'CLOSED', 'DISMISSED_DATA_ISSUE'}:
        care_runtime.trace(session, goal, 'human_escalation', reason, risk_event_id=str(risk.id))
        return risk
    source = 'autonomy_attention:' + str(goal.id)
    row = session.scalar(select(Task).where(Task.patient_id == goal.member_id, Task.source == source))
    if row is None:
        program_id = goal.context_json.get('program_id')
        row = task(session, goal.member_id, UUID(program_id) if program_id else None,
            '自动处理未完成，需要人工检查', reason, goal.owner or '健康管理师', utc_now(), source)
        care_runtime.trace(session, goal, 'human_escalation', reason, task_id=str(row.id))
    return row
