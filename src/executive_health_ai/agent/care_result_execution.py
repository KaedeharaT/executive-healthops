"""Existing worker's detached semantic action with a durable, fenced lease."""
from datetime import date, timedelta
from uuid import uuid4
from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session
from executive_health_ai.models import AgentGoal
from executive_health_ai.models.base import utc_now
from executive_health_ai.llm.local_llm_client import LocalLLMSettings
from executive_health_ai.llm.activity import collect_calls, observe_progress
from executive_health_ai.services import care_runtime as runtime


def execute(supervisor,session,goal):
    if goal.status not in {'RUNNING','PROCESSING'} or goal.automation_paused:return goal
    token=uuid4().hex;now=utc_now()
    lease=timedelta(seconds=LocalLLMSettings.from_environment().timeout_seconds+120)
    context={**goal.context_json,'execution':{'token':token,'started_at':now.isoformat()},'progress_events':{}}
    count=session.execute(update(AgentGoal).where(AgentGoal.id==goal.id,AgentGoal.automation_paused.is_(False),
        or_(AgentGoal.status=='RUNNING',and_(AgentGoal.status=='PROCESSING',AgentGoal.next_check_at<=now)))
        .values(status='PROCESSING',next_check_at=now+lease,context_json=context)).rowcount
    goal_id=goal.id;session.commit()
    if not count:return goal
    # No Session transaction survives into file/network/model work.
    binding=session.get_bind()
    owner=(AgentGoal.id==goal_id,AgentGoal.status=='PROCESSING',AgentGoal.automation_paused.is_(False),
        AgentGoal.context_json['execution']['token'].as_string()==token)
    def progress(event):
        context['progress_events']={**context['progress_events'],event:utc_now().isoformat()}
        with Session(binding) as short:
            short.execute(update(AgentGoal).where(*owner).values(context_json=context))
            short.commit()
    try:
        from executive_health_ai.services.care_result_extraction import extract
        with collect_calls() as calls,observe_progress(progress):
            parsed=extract(context['text'],today=date.fromisoformat(context['recorded_date']),source_id=context['event_id'])
        held=session.execute(update(AgentGoal).where(*owner).values(next_check_at=None)).rowcount
        if not held:session.rollback();return session.get(AgentGoal,goal_id)
        session.refresh(goal)
        goal.context_json={**context,'parsed':parsed,'execution':{}}
        from executive_health_ai.agent.activity_audit import llm_calls
        llm_calls(session,goal,calls,accepted=not parsed['warning'],sources=['health_event:'+context['event_id']],
            result_count=len(parsed['facts'])+len(parsed['actions']))
        runtime.step_done(session,goal,'整理处理结果',{'facts':len(parsed['facts']),'actions':len(parsed['actions'])})
        goal.current_stage='确认后续安排'
        runtime.wait(session,goal,'WAITING_MANAGER',next_action='核对本次管理记录和后续安排，确认后统一保存',
            expected_event='MANAGER_RESULT_CONFIRMED',expected_source=goal.id)
        session.commit();return goal
    except BaseException:
        session.rollback()
        attempts=int(context.get('execution_failures',0))+1
        session.execute(update(AgentGoal).where(*owner).values(status='FAILED' if attempts>=3 else 'RUNNING',
            next_check_at=None,context_json={**context,'execution_failures':attempts},
            next_action='本次整理未完成，原文已保留，请由管理员核对异常后恢复' if attempts>=3 else '正在恢复本次结果整理'))
        session.commit()
        raise
