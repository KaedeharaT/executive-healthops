"""Due-object routing over the existing worker, goals and management services."""
from datetime import datetime, time, timezone
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import AgentGoal, Task, HealthProgram, ProgramPhase, ServiceRequest, Patient
from executive_health_ai.models.management_workflow import RecheckPlan
from executive_health_ai.models.base import utc_now
from executive_health_ai.services import care_runtime as runtime
from executive_health_ai.services.management_action_loop import ManagementActionLoop, CLOSED


def schedule_due(session, now):
    """Query bounded due work, never send raw observations or all members to AI."""
    from executive_health_ai.services.health_events import ingest_health_event
    count=0
    sources=((Task,Task.due_at,'task'),(RecheckPlan,RecheckPlan.planned_at,'recheck'),
        (ServiceRequest,ServiceRequest.scheduled_at,'service'))
    for model,column,kind in sources:
        rows=session.scalars(select(model).join(Patient,Patient.id==model.patient_id)
            .where(Patient.archived_at.is_(None),column.is_not(None),column<=now,
                model.status.not_in(CLOSED)).order_by(column).limit(100))
        for row in list(rows):
            if kind=='task' and (row.responsible_role=='doctor' or row.risk_event_id):continue
            due=getattr(row,column.key)
            _,created=ingest_health_event(session,member_id=row.patient_id,event_type='TIME_DUE',
                event_category='TIME_DUE',source_type='SYSTEM',
                source_id=f'{kind}:{row.id}:{due.isoformat()}',occurred_at=due,
                payload_ref={'work_kind':kind,'work_id':str(row.id),'due_at':due.isoformat()},dispatch=False)
            count+=int(created)
    phases=session.execute(select(ProgramPhase,HealthProgram).join(HealthProgram,HealthProgram.id==ProgramPhase.program_id)
        .join(Patient,Patient.id==HealthProgram.patient_id).where(Patient.archived_at.is_(None),
            ProgramPhase.status=='ACTIVE',ProgramPhase.end_date<=now.date()).limit(100))
    for phase,p in list(phases):
        _,created=ingest_health_event(session,member_id=p.patient_id,event_type='TIME_DUE',
            event_category='TIME_DUE',source_type='SYSTEM',source_id='phase:'+str(phase.id),
            payload_ref={'work_kind':'phase','work_id':str(phase.id),'program_id':str(p.id)},dispatch=False)
        count+=int(created)
    # Explicit waits also use the same event ledger, not in-memory timers.
    for goal in list(session.scalars(select(AgentGoal).where(AgentGoal.status=='WAITING_TIME',
            AgentGoal.next_check_at<=now,AgentGoal.automation_paused.is_(False)))):
        bound=goal.context_json.get('wait',{})
        _,created=ingest_health_event(session,member_id=goal.member_id,event_type='TIME_DUE',
            event_category='TIME_DUE',source_type='SYSTEM',source_id=bound.get('source') or str(goal.id),
            occurred_at=goal.next_check_at,payload_ref={'resume_goal_id':str(goal.id)},dispatch=False)
        count+=int(created)
    return count


def on_event(session, event, supervisor):
    payload=event.payload_ref or {}
    if event.event_type=='FOLLOWUP_RESULT_RECORDED':
        from executive_health_ai.services.care_results import from_event
        return from_event(session,event,supervisor)
    if identity:=payload.get('resume_goal_id'):
        goal=session.get(AgentGoal,UUID(identity))
        if not goal or goal.member_id!=event.member_id:raise ValueError('等待事项不属于此会员。')
        if runtime.resume(session,goal,event_type=event.event_type,source_id=event.source_id):
            advance(session,goal,supervisor)
        return goal
    from executive_health_ai.services.member_management_projection import MemberManagementProjection
    view=MemberManagementProjection().member(session,event.member_id)
    from executive_health_ai.services.risk_autonomy import evaluate_event
    risk = evaluate_event(session, event)
    # Compatibility receipts without a concrete operation remain wake/check.
    # A missing annual program must never suppress a formal RED/YELLOW event.
    if not view.program and not (risk and event.event_category == 'MEANINGFUL_CHANGE'):return None
    if event.event_type=='MANAGEMENT_ITEM_COMPLETED':
        for current in list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==event.member_id,
                AgentGoal.goal_type=='DAILY_CARE',AgentGoal.status=='WAITING_MANAGER'))):
            refs=current.context_json.get('work_refs',[])
            if event.source_id in refs:
                runtime.resume(session,current,event_type=event.event_type,source_id=event.source_id)
                advance(session,current,supervisor)
        return maybe_stage(session,event.member_id,view.program.id,event.id,supervisor)
    if payload.get('work_kind')=='phase':
        return maybe_stage(session,event.member_id,view.program.id,event.id,supervisor)
    if not payload.get('work_id') and event.event_category!='MEANINGFUL_CHANGE':return None
    if risk and event.event_category == 'MEANINGFUL_CHANGE':
        existing = next((g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id == event.member_id,
            AgentGoal.goal_type == 'DAILY_CARE', AgentGoal.status.not_in(('COMPLETED', 'CANCELLED'))))
            if g.context_json.get('risk_event_id') == str(risk.id)), None)
        if existing:
            return existing
    goal=runtime.start(session,supervisor,member_id=event.member_id,kind='DAILY_CARE',source_id=event.id,
        title='核对本次到期工作' if event.event_category=='TIME_DUE' else '核对健康变化与后续安排',
        context={'program_id':str(view.program.id) if view.program else None,'event_id':str(event.id),
            'trigger_reason':event.description,'trigger_source':event.source,'event_payload':payload,
            'meaningful_change':event.event_category=='MEANINGFUL_CHANGE',
            **({'risk_event_id': str(risk.id)} if risk else {})},owner=view.owner if view.program else '健康管理师')
    advance(session,goal,supervisor)
    return goal


def advance(session,goal,supervisor):
    """Persist bounded retries in the existing goal, never spin a failed action."""
    from executive_health_ai.services.autonomy import AutonomyGate
    from datetime import timedelta
    if goal.status != 'RUNNING' or goal.automation_paused:
        return goal
    if goal.next_check_at and goal.next_check_at > utc_now():
        return goal
    try:
        return _advance(session, goal, supervisor)
    except AutonomyGate as exc:
        state = 'WAITING_DOCTOR' if exc.decision.required_role == 'DOCTOR' else 'WAITING_MANAGER'
        runtime.wait(session, goal, state, next_action=str(exc))
        from executive_health_ai.services.autonomy_attention import attention
        attention(session, goal, str(exc))
        return goal
    except Exception as exc:
        count = int(goal.context_json.get('automation_failures', 0)) + 1
        goal.context_json = {**goal.context_json, 'automation_failures': count}
        runtime.trace(session, goal, 'automation_failed', '自动处理暂未完成',
            attempt=count, error=type(exc).__name__ + ': ' + str(exc)[:240])
        if count > supervisor.default_max_retries:
            runtime.wait(session, goal, 'WAITING_MANAGER', next_action='自动处理未完成，需要人工检查。')
            from executive_health_ai.services.autonomy_attention import attention
            attention(session, goal, goal.next_action)
        else:
            goal.next_check_at = utc_now() + timedelta(seconds=2 ** count)
        return goal


def _advance(session,goal,supervisor):
    if goal.status!='RUNNING' or goal.automation_paused:return goal
    if goal.goal_type!='DAILY_CARE':return goal
    context=goal.context_json
    for label,tool in [('核对当前阶段','get_current_phase'),('核对到期事项','get_open_management_items'),('核对医生意见','get_doctor_review')]:
        goal.current_stage=label
        result=supervisor.registry.execute(session,tool,goal,{'program_id':context['program_id']})
        runtime.step_done(session,goal,label,result)
    payload=context.get('event_payload',{})
    if context.get('risk_event_id') and context.get('meaningful_change'):
        from executive_health_ai.services.risk_autonomy import advance as govern
        return govern(session, goal, supervisor)
    kind=payload.get('work_kind');identity=payload.get('work_id')
    model={'task':Task,'recheck':RecheckPlan,'service':ServiceRequest}.get(kind)
    work=session.get(model,UUID(identity)) if model and identity else None
    if work and work.patient_id!=goal.member_id:raise ValueError('工作事项不属于此会员。')
    if work and work.status not in CLOSED:
        if kind == 'task' and work.responsible_role == 'system' and work.source == 'approved_plan_check':
            from executive_health_ai.services.autonomy import current_risk
            risk = current_risk(session, goal.member_id)
            if risk and risk.risk_level == 'GREEN':
                supervisor.registry.execute(session, 'execute_approved_plan_check', goal,
                    {'task_id': str(work.id), 'idempotency_key': 'plan-check:' + str(work.id)})
                goal.context_json = {**context, 'work_refs': [str(work.id)]}
                return runtime.finish(session, goal)
        if payload.get('due_at'):
            actual=getattr(work,'due_at',None) or getattr(work,'planned_at',None) or getattr(work,'scheduled_at',None)
            if actual and actual.isoformat()!=payload['due_at']:
                goal.context_json={**context,'no_action_reason':'原事项已改期，等待新的计划时间'}
                return runtime.finish(session,goal)
        # Original task / recheck / service remains the only human work row.
        goal.context_json={**context,'work_refs':[str(work.id)] if kind=='task' else [],
            'related_work':{'kind':kind,'id':str(work.id)}}
        goal.current_stage='等待处理结果'
        runtime.wait(session,goal,'WAITING_MANAGER',next_action='请处理原有到期事项并记录本次结果',
            expected_event='MANAGEMENT_ITEM_COMPLETED',expected_source=work.id)
        return goal
    if context.get('meaningful_change') and not context.get('work_refs'):
        # A rule finding is not a diagnosis; ask a manager to check evidence.
        result=supervisor.registry.execute(session,'create_followup',goal,{
            'program_id':context['program_id'],'title':'核对健康数据变化',
            'instruction':'核对设备来源和变化依据；涉及医学意义时提交医生，不据此诊断。',
            'due_at':utc_now().isoformat(),'source_reference':'health_event:'+context['event_id'],
            'idempotency_key':'meaningful-change'})
        goal.context_json={**context,'work_refs':[result['task_id']]}
        goal.current_stage='等待处理结果'
        runtime.wait(session,goal,'WAITING_MANAGER',next_action='核对变化依据，记录结果；医学判断交由医生',
            expected_event='MANAGEMENT_ITEM_COMPLETED',expected_source=result['task_id'])
        return goal
    if not context.get('work_refs'):
        goal.context_json={**context,'no_action_reason':'原事项已结束，无需重复安排'}
    return runtime.finish(session,goal)


def maybe_stage(session,member_id,program_id,source_id,supervisor):
    state=ManagementActionLoop().project(session,member_id,program_id)
    if not state['review_ready']:return None
    phase=state['phase']
    goal=runtime.start(session,supervisor,member_id=member_id,kind='STAGE_REVIEW',source_id=phase.id,
        title='核对阶段结果并准备下一阶段',owner=state['view'].owner,
        context={'program_id':str(program_id),'phase_id':str(phase.id),'event_id':str(source_id),
            'trigger_reason':'本阶段已到复盘节点','trigger_source':'系统业务结果'})
    if goal.status!='RUNNING':return goal
    for label,tool in [('汇总阶段记录','get_recent_management_logs'),('准备阶段复盘','prepare_stage_review')]:
        result=supervisor.registry.execute(session,tool,goal,{'program_id':str(program_id)})
        runtime.step_done(session,goal,label,result)
        if tool=='prepare_stage_review':goal.context_json={**goal.context_json,'stage_summary':result['summary']}
    goal.current_stage='确认阶段结果'
    runtime.wait(session,goal,'WAITING_MANAGER',next_action='核对阶段汇总，确认下一阶段安排',
        expected_event='STAGE_REVIEW_CONFIRMED',expected_source=phase.id)
    return goal


def work_completed(session,member_id,source_id):
    from executive_health_ai.services.health_events import ingest_health_event
    return ingest_health_event(session,member_id=member_id,event_type='MANAGEMENT_ITEM_COMPLETED',
        event_category='NEW_INFORMATION',source_type='SYSTEM',source_id=str(source_id))


def reconcile(session,supervisor):
    """Observe existing object results without creating a second human queue."""
    for goal in list(session.scalars(select(AgentGoal).where(AgentGoal.goal_type=='DAILY_CARE',
            AgentGoal.status=='WAITING_MANAGER',AgentGoal.automation_paused.is_(False)))):
        if goal.context_json.get('risk_event_id') and goal.context_json.get('wait', {}).get('event') == 'RISK_RESOLVED':
            from executive_health_ai.models import RiskEvent
            risk = session.get(RiskEvent, UUID(goal.context_json['risk_event_id']))
            if risk and risk.status in {'CLOSED', 'DISMISSED_DATA_ISSUE'}:
                runtime.resume(session, goal, event_type='RISK_RESOLVED', source_id=risk.id)
                advance(session, goal, supervisor)
            continue
        related=goal.context_json.get('related_work',{})
        kind=related.get('kind');identity=related.get('id')
        model={'task':Task,'recheck':RecheckPlan,'service':ServiceRequest}.get(kind)
        row=session.get(model,UUID(identity)) if model and identity else None
        if row and row.status in CLOSED:
            work_completed(session,goal.member_id,row.id)
            if goal.status=='WAITING_MANAGER':
                runtime.resume(session,goal,event_type='MANAGEMENT_ITEM_COMPLETED',source_id=row.id)
                advance(session,goal,supervisor)
