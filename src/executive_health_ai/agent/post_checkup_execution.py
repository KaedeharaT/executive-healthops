"""Short claim/write transactions around existing post-checkup optional AI.

Executed by the existing scheduler, never a second worker or planning policy.
"""
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import update, and_, or_
from executive_health_ai.models import AgentGoal
from executive_health_ai.models.base import utc_now
from executive_health_ai.llm.local_llm_client import LocalLLMClient, LocalLLMSettings, sanitize_for_llm
from executive_health_ai.llm.activity import collect_calls
from executive_health_ai.agent import post_checkup as flow, activity_audit


def execute(supervisor,session,goal):
    if not goal.context_json.get('pending_ai') or goal.automation_paused:return goal
    if goal.status not in {'RUNNING','PROCESSING'}:return goal
    context=deepcopy(goal.context_json);token=uuid4().hex;now=utc_now()
    task=context['pending_ai']['kind'];context['pending_ai']={**context['pending_ai'],'token':token}
    context['progress_events']={**context.get('progress_events',{}),'AI_REQUEST_STARTED':now.isoformat()}
    claimed=session.execute(update(AgentGoal).where(AgentGoal.id==goal.id,AgentGoal.automation_paused.is_(False),
        or_(AgentGoal.status=='RUNNING',and_(AgentGoal.status=='PROCESSING',AgentGoal.next_check_at<=now)))
        .values(status='PROCESSING',context_json=context,next_action='本地AI正在整理有来源依据的资料',next_check_at=now+timedelta(seconds=LocalLLMSettings.from_environment().timeout_seconds+120))).rowcount
    goal_id,source_id=goal.id,goal.source_id
    session.commit()
    if not claimed:session.refresh(goal);return goal
    try:
        # No session access, ORM flush, network-backed knowledge or transaction
        # across this call. Outputs remain non-clinical drafts with original checks.
        with collect_calls() as calls:
            if task=='summary':summary,status=flow.llm_summary(context)
            else:
                accepted=False;actions=deepcopy(context['actions'])
                try:
                    result=context['doctor_result']
                    response=LocalLLMClient().generate_structured(task='post_checkup_action_draft',
                        system_prompt='从医生建议中提取一个随访主题。只返回 {"quote":"建议原文中连续的短句"}。不得新增医学决定、处方或日期。',
                        user_prompt=sanitize_for_llm(result['recommendation'])[:1800],document_id=source_id,page=0)
                    quote=response.get('quote','')
                    if isinstance(quote,str) and 2<=len(quote)<=30 and quote in result['recommendation']:
                        actions[1]['title']='随访：'+quote;accepted=True
                except Exception:
                    pass  # Existing optional AI fallback; deterministic actions survive.
                status='AVAILABLE' if accepted else 'UNAVAILABLE'
        owner=and_(AgentGoal.id==goal_id,AgentGoal.status=='PROCESSING',AgentGoal.automation_paused.is_(False),AgentGoal.context_json['pending_ai']['token'].as_string()==token)
        claim=session.execute(update(AgentGoal).where(owner).values(next_check_at=None)).rowcount
        if claim!=1:session.rollback();session.refresh(goal);return goal
        session.refresh(goal)
        context={k:v for k,v in goal.context_json.items() if k!='pending_ai'}
        context['progress_events']={**context.get('progress_events',{}),'AI_REQUEST_FINISHED':utc_now().isoformat()}
        if task=='summary':
            context.update(summary=summary,llm_status=status,ai_summary_draft=summary if status=='AVAILABLE' else None)
        else:context['actions']=actions
        goal.context_json=context
        activity_audit.llm_calls(session,goal,calls,accepted=status=='AVAILABLE',sources=['体检报告'] if task=='summary' else ['已确认医生建议原文'])
        if task=='summary':
            flow.move(supervisor,session,goal,'WAITING_MANAGER_REVIEW','确认本次健康变化和建议处理路径',
                status='WAITING_MANAGER' if context.get('program_id') and goal.owner else 'WAITING_INPUT')
        else:flow.move(supervisor,session,goal,'WAITING_ACTION_APPROVAL','确认并创建后续安排')
        session.commit();return goal
    except BaseException:
        session.rollback()
        session.execute(update(AgentGoal).where(AgentGoal.id==goal_id,AgentGoal.status=='PROCESSING',AgentGoal.automation_paused.is_(False),AgentGoal.context_json['pending_ai']['token'].as_string()==token)
            .values(status='RUNNING',next_check_at=None))
        session.commit();raise
