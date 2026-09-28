"""Runtime transaction boundary for the existing intake policy.

UI and worker opt in with a dedicated session. Claim/progress commits are short;
source extraction and model requests hold no database write lock. Candidate
results and the plan transition still commit together. Ordinary command callers
retain their caller-owned transaction through profile_intake.advance.
"""
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session
from executive_health_ai.models import AgentGoal, AgentPlanStep
from executive_health_ai.models.base import utc_now
from executive_health_ai.llm.activity import observe_progress
from executive_health_ai.llm.local_llm_client import LocalLLMSettings


class ClaimLost(RuntimeError):
    """An expired execution cannot persist over its replacement."""


def execute(supervisor, session, goal):
    from executive_health_ai.agent.profile_intake import advance
    if goal.automation_paused or goal.status not in {'RUNNING', 'PROCESSING'}:
        return goal
    now=utc_now()
    token=uuid4().hex
    lease=timedelta(seconds=LocalLLMSettings.from_environment().timeout_seconds+120)
    context={**goal.context_json, 'execution': {'token':token, 'event':'RUNNING', 'started_at':now.isoformat(), 'event_at':now.isoformat()}}
    if goal.current_stage=='PARSING':
        context['progress_events']={'PARSING_STARTED':now.isoformat()}
    claimed=session.execute(update(AgentGoal).where(
        AgentGoal.id==goal.id, AgentGoal.current_stage==goal.current_stage,
        AgentGoal.automation_paused.is_(False),
        or_(AgentGoal.status=='RUNNING', and_(AgentGoal.status=='PROCESSING',
            AgentGoal.next_check_at.is_not(None), AgentGoal.next_check_at<=now))
    ).values(status='PROCESSING',next_check_at=now+lease,context_json=context),
        execution_options={'synchronize_session':False}).rowcount
    if claimed:
        session.execute(update(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id,
            AgentPlanStep.step_type==goal.current_stage,AgentPlanStep.started_at.is_(None)).values(started_at=now))
    # Publishing the claim makes a second browser/worker observe PROCESSING.
    # Never keep the CAS write transaction open across extraction/model I/O.
    session.commit()
    session.refresh(goal)
    if not claimed:return goal
    owner=and_(AgentGoal.id==goal.id,AgentGoal.status=='PROCESSING',
        AgentGoal.context_json['execution']['token'].as_string()==token)

    def progress(event):
        if goal.current_stage!='PARSING':return
        if event=='BEFORE_PERSIST':
            # Fence stale results before any candidate is flushed. This short
            # write transaction lasts only through result persistence.
            with session.no_autoflush:
                held=session.execute(update(AgentGoal).where(owner).values(next_check_at=utc_now()+lease),
                    execution_options={'synchronize_session':False}).rowcount
            if not held:raise ClaimLost('Intake execution was superseded.')
            return
        # A separate short transaction publishes actual worker progress without
        # flushing the parser's pending ORM metadata or unconfirmed candidates.
        at=utc_now().isoformat()
        context['progress_events']={**context.get('progress_events',{}),event:at}
        context['execution']={**context['execution'],'event':event,'event_at':at}
        with Session(session.get_bind()) as status:
            updated=status.execute(update(AgentGoal).where(owner).values(
                context_json=context,
                next_check_at=utc_now()+lease)).rowcount
            status.commit()
        if not updated:raise ClaimLost('Intake execution was superseded.')

    try:
        with observe_progress(progress,chain=True):
            result=advance(supervisor,session,goal,claimed=True)
        result.context_json={**{k:v for k,v in result.context_json.items() if k!='execution'},
                             'progress_events':context.get('progress_events',{})}
        result.next_check_at=None
        session.commit()
        return result
    except ClaimLost:
        session.rollback()
        session.refresh(goal)
        return goal
    except BaseException:
        # Release only our claim after rollback; retain the traceback for actual
        # failures. A killed process is recovered after its bounded lease expires.
        session.rollback()
        session.execute(update(AgentGoal).where(owner).values(status='RUNNING',next_check_at=None,
            context_json={k:v for k,v in context.items() if k!='execution'}),
            execution_options={'synchronize_session':False})
        session.commit()
        raise
