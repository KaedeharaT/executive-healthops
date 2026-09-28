"""Persistence and completion contracts for bounded longitudinal care goals.

No worker or task state machine lives here. The existing supervisor/scheduler
calls these short commands; business mutations always go through its registry.
"""
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import AgentGoal, AgentPlanStep, AgentRunTrace, Task
from executive_health_ai.models.management_workflow import ManagementLog, StageReview
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.member_agents import ensure_member_agent

KINDS = {'DAILY_CARE', 'FOLLOWUP_RESULT', 'STAGE_REVIEW'}
WAITS = {'WAITING_MANAGER', 'WAITING_DOCTOR', 'WAITING_MEMBER', 'WAITING_TIME', 'WAITING_INPUT'}


def trace(session, goal, action, summary, **refs):
    session.add(AgentRunTrace(goal_id=goal.id, plan_id=goal.current_plan_id, action=action,
        status='COMPLETED', completed_at=utc_now(), result_summary=summary, metadata_json=refs))
    session.flush()


def start(session, supervisor, *, member_id, kind, source_id, title, context, owner):
    if kind not in KINDS: raise ValueError('不支持此管理流程。')
    agent = ensure_member_agent(session, member_id)
    prior = session.scalar(select(AgentGoal).where(AgentGoal.goal_type == kind,
        AgentGoal.source_type == 'health_event', AgentGoal.source_id == str(source_id)))
    if prior:
        if prior.member_id != member_id: raise ValueError('流程不属于此会员。')
        return prior
    goal = AgentGoal(member_id=member_id, goal_type=kind, source_type='health_event',
        source_id=str(source_id), title=title, status='RUNNING', owner=owner,
        context_json={**context, 'member_agent_id':str(agent.id)}, success_criteria={'business_result':False})
    session.add(goal);session.flush()
    supervisor.planner.create_plan(session, goal, reason=context.get('trigger_reason') or title)
    steps = supervisor.planner.steps(session, goal.current_plan_id)
    goal.current_stage=steps[0].step_type
    trace(session, goal, 'goal_started', title, member_agent_id=str(agent.id), source_id=str(source_id))
    return goal


def step_done(session, goal, label, result=None):
    row=session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id,
        AgentPlanStep.step_type==label))
    if not row: raise ValueError('处理步骤不属于本次流程。')
    row.status='COMPLETED'; row.started_at=row.started_at or utc_now(); row.completed_at=utc_now()
    if result is not None:
        import json
        row.result_summary=json.dumps(result,ensure_ascii=False,default=str)
    session.flush()


def wait(session, goal, state, *, next_action, due=None, expected_event=None, expected_source=None):
    if state not in WAITS: raise ValueError('等待状态无效。')
    if state=='WAITING_TIME' and (due is None or due.tzinfo is None): raise ValueError('等待时间需要明确时区。')
    goal.status=state;goal.next_action=next_action;goal.next_check_at=due
    goal.context_json={**goal.context_json,'wait':{'state':state,'event':expected_event,
        'source':str(expected_source) if expected_source else None,'since':utc_now().isoformat()}}
    trace(session,goal,'wait',next_action,state=state,due=due.isoformat() if due else None)


def resume(session, goal, *, event_type, source_id):
    bound=goal.context_json.get('wait',{})
    if goal.status not in WAITS: return False
    if bound.get('event') != event_type or bound.get('source') != str(source_id):
        raise ValueError('返回结果与原等待事项不匹配。')
    if goal.status=='WAITING_TIME' and goal.next_check_at and goal.next_check_at>utc_now():return False
    goal.status='RUNNING';goal.next_check_at=None
    goal.context_json={**goal.context_json,'wait':{},'resumed_at':utc_now().isoformat()}
    trace(session,goal,'resume','收到原事项结果，继续处理',event_type=event_type,source_id=str(source_id))
    return True


def finish(session, goal):
    """A completed plan alone never proves a business outcome."""
    ctx=goal.context_json
    valid=False
    if goal.goal_type=='DAILY_CARE':
        refs=ctx.get('work_refs',[])
        valid=bool(ctx.get('no_action_reason')) if not refs else all(
            (row:=session.get(Task,UUID(key))) is not None and row.patient_id==goal.member_id
            and row.status in {'COMPLETED','CANCELLED'} for key in refs)
    elif goal.goal_type=='FOLLOWUP_RESULT':
        row=session.get(ManagementLog,UUID(ctx['log_id'])) if ctx.get('log_id') else None
        valid=bool(row and row.patient_id==goal.member_id and ctx.get('actions_verified'))
    elif goal.goal_type=='STAGE_REVIEW':
        from executive_health_ai.models import ProgramPhase
        review=session.get(StageReview,UUID(ctx['review_id'])) if ctx.get('review_id') else None
        following=session.get(ProgramPhase,UUID(ctx['next_phase_id'])) if ctx.get('next_phase_id') else None
        valid=bool(review and review.patient_id==goal.member_id and following
            and following.program_id==review.program_id and following.status=='ACTIVE')
    if not valid: raise ValueError('真实业务结果尚未满足完成条件。')
    goal.status='COMPLETED';goal.completed_at=utc_now();goal.next_check_at=None
    goal.success_criteria={'business_result':True}
    goal.next_action='本次管理已完成，继续等待新的资料、结果或计划时间'
    for step in session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id)):
        step.status='COMPLETED';step.completed_at=step.completed_at or utc_now()
    trace(session,goal,'goal_completed',goal.next_action,result_references={k:ctx[k] for k in
        ('log_id','review_id','next_phase_id','work_refs','no_action_reason') if k in ctx})
    return goal
