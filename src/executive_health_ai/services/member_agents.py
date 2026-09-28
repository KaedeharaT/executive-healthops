"""One durable member identity; bounded capabilities remain in the supervisor."""
from uuid import UUID
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from executive_health_ai.models import MemberAgent, AgentGoal, HealthEvent, AgentPlanStep
from executive_health_ai.models.base import utc_now


def ensure_member_agent(session: Session, member_id: UUID) -> MemberAgent:
    from executive_health_ai.services.member_archive import require_active
    require_active(session,member_id)
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{member_id})
    prior=session.scalar(select(MemberAgent).where(MemberAgent.member_id==member_id))
    if prior:return prior
    try:
        with session.begin_nested():
            row=MemberAgent(member_id=member_id)
            session.add(row);session.flush()
    except IntegrityError:
        row=session.scalar(select(MemberAgent).where(MemberAgent.member_id==member_id))
        if row is None:raise
    return row


def goal_state(goal,session=None):
    if goal.status in {'RUNNING','PROCESSING','WRITING','ACTIVE'}:return 'RUNNING'
    if goal.status in {'FAILED','ESCALATED','BLOCKED'}:return 'FAILED'
    if goal.status in {'WAITING_MANAGER','WAITING_DOCTOR','WAITING_MEMBER','WAITING_TIME'}:return goal.status
    if goal.status=='WAITING_INPUT':return 'WAITING_MANAGER'
    if goal.status=='WAITING' and session is not None:
        step=session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id,
            AgentPlanStep.status.in_(('WAITING_DOCTOR','WAITING_MEMBER','WAITING_MANAGER'))).order_by(AgentPlanStep.step_order))
        if step:return step.status
    return 'WAITING_TIME' if goal.next_check_at else 'WAITING_MANAGER'


def synchronize(session, member_id):
    """Read all existing goals: completing one must not hide another active goal."""
    row=session.scalar(select(MemberAgent).where(MemberAgent.member_id==member_id))
    if not row:return
    goals=list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==member_id,
        AgentGoal.status.not_in(('COMPLETED','CANCELLED')))))
    order={'RUNNING':0,'WAITING_DOCTOR':1,'WAITING_MANAGER':2,'FAILED':3,'WAITING_MEMBER':4,'WAITING_TIME':5}
    next_wake=session.scalar(select(func.min(HealthEvent.occurred_at)).where(HealthEvent.member_id==member_id,
        HealthEvent.event_category=='TIME_DUE',HealthEvent.status=='PENDING'))
    states={g.id:goal_state(g,session) for g in goals}
    goal=min(goals,key=lambda g:(order[states[g.id]],g.started_at),default=None)
    if goal and goal.next_check_at:next_wake=min(filter(None,(next_wake,goal.next_check_at)))
    state=states[goal.id] if goal else ('WAITING_TIME' if next_wake else 'IDLE')
    values=dict(status=state,
        current_goal_id=goal.id if goal else None,waiting_for=state.removeprefix('WAITING_') if state.startswith('WAITING_') else None,
        next_wake_at=next_wake)
    if any(getattr(row,key)!=value for key,value in values.items()):
        session.execute(update(MemberAgent).where(MemberAgent.id==row.id).values(**values,updated_at=utc_now()))


def wake(session,row,event):
    session.execute(update(MemberAgent).where(MemberAgent.id==row.id).values(status='RUNNING',waiting_for=None,
        last_event_at=event.occurred_at,last_active_at=utc_now(),wake_count=MemberAgent.wake_count+1,updated_at=utc_now()))
