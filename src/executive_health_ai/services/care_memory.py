"""Sourced fact, working and longitudinal views; no duplicate medical store."""
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import AgentGoal,AgentPlanStep,AgentRunTrace
from executive_health_ai.models.management_workflow import ManagementLog
from executive_health_ai.services import care_runtime


def facts(session,member_id):
    from executive_health_ai.services.longitudinal import HealthAssessmentService
    return HealthAssessmentService().current_profile(session,member_id)


def working(session,goal):
    steps=session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id).order_by(AgentPlanStep.step_order))
    tools=session.scalars(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.action=='tool_execution'))
    return {'reason':goal.context_json.get('trigger_reason'),'completed_steps':[s.step_type for s in steps if s.status=='COMPLETED'],
        'waiting':goal.context_json.get('wait',{}),'next':goal.next_action,
        'tool_result_references':[{'trace_id':str(t.id),'tool':t.tool_name,'status':t.status} for t in tools]}


def remember_result(session,goal):
    identity=goal.context_json.get('log_id')
    row=session.get(ManagementLog,UUID(identity)) if identity else None
    if not row or row.patient_id!=goal.member_id:return
    if session.scalar(select(AgentRunTrace).where(AgentRunTrace.goal_id==goal.id,AgentRunTrace.action=='care_context')):return
    topics={'夜班':'会员提及夜班，后续沟通需核对可行时间','出差':'会员提及出差，后续安排需核对时间',
        '联系不上':'本次未联系到会员，需继续核对联系安排'}
    found=[summary for key,summary in topics.items() if key in row.result]
    if found:care_runtime.trace(session,goal,'care_context','；'.join(found),source_type='ManagementLog',
        source_id=str(row.id),occurred_at=row.occurred_at.isoformat())


def longitudinal(session,member_id):
    rows=session.scalars(select(AgentRunTrace).join(AgentGoal,AgentGoal.id==AgentRunTrace.goal_id)
        .where(AgentGoal.member_id==member_id,AgentRunTrace.action=='care_context').order_by(AgentRunTrace.started_at.desc()).limit(30))
    return [{'summary':r.result_summary,'source':r.metadata_json,'recorded_at':r.started_at.isoformat()} for r in rows]
