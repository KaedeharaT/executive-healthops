"""Business result input and confirmed writeback through existing service tools."""
from datetime import date, datetime, time, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from sqlalchemy import select
from executive_health_ai.models import AgentGoal, Task, HealthProgram, DoctorReview, Patient
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.management_workflow import owned, required
from executive_health_ai.services import care_runtime as runtime


def submit(session,*,member_id,program_id,task_id,text,actor,outcome,request_key):
    from executive_health_ai.services.health_events import ingest_health_event
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{member_id})
    item=owned(session,Task,task_id,member_id)
    p=owned(session,HealthProgram,program_id,member_id)
    if item.program_id not in {None,p.id} or item.risk_event_id or item.responsible_role=='doctor':
        raise ValueError('请使用该事项原有医学或风险处理入口。')
    if outcome not in {'已完成','部分完成','未完成'}:raise ValueError('请选择处理结果状态。')
    text=required(text,'本次处理结果')
    if len(text)>6000:raise ValueError('本次处理结果请控制在6000字以内。')
    pending=next((g for g in session.scalars(select(AgentGoal).where(AgentGoal.member_id==member_id,
        AgentGoal.goal_type=='FOLLOWUP_RESULT',AgentGoal.status.not_in(('COMPLETED','CANCELLED'))))
        if g.context_json.get('task_id')==str(task_id)),None)
    if pending:
        if pending.context_json.get('text')!=text or pending.context_json.get('outcome')!=outcome:
            raise ValueError('此事项已有待核对结果，请先处理当前结果。')
        return pending
    event,_=ingest_health_event(session,member_id=member_id,event_type='FOLLOWUP_RESULT_RECORDED',
        event_category='NEW_INFORMATION',source_type='MANUAL',source_id=request_key,
        payload_ref={'program_id':str(p.id),'task_id':str(item.id),'text':text,'actor':actor,'outcome':outcome})
    if event.payload_ref.get('text')!=text:raise ValueError('同一提交不能改成不同处理结果。')
    return session.get(AgentGoal,event.goal_id)


def from_event(session,event,supervisor):
    p=event.payload_ref
    program=owned(session,HealthProgram,p['program_id'],event.member_id)
    item=owned(session,Task,p['task_id'],event.member_id)
    if item.program_id not in {None,program.id} or item.responsible_role=='doctor' or item.risk_event_id:
        raise ValueError('不能通过结果整理代替医学判断。')
    if item.status in {'COMPLETED','CANCELLED'}:raise ValueError('原事项已结束，请查看已有结果。')
    member_zone=session.get(Patient,event.member_id).timezone
    goal=runtime.start(session,supervisor,member_id=event.member_id,kind='FOLLOWUP_RESULT',source_id=event.id,
        title='整理本次处理结果并准备后续安排',owner=p['actor'],
        context={**p,'event_id':str(event.id),'recorded_date':event.occurred_at.astimezone(ZoneInfo(member_zone)).date().isoformat(),
            'time_zone':member_zone,
            'trigger_reason':'收到本次工作处理结果','trigger_source':'健管记录'})
    runtime.step_done(session,goal,'接收处理结果')
    goal.current_stage='整理处理结果';goal.next_action='正在整理原文中的事实和后续安排'
    return goal


def proposals(session,goal):
    """Attach an existing doctor's evidence, never invent a medical instruction."""
    data=goal.context_json.get('parsed',{})
    reviews=list(session.scalars(select(DoctorReview).where(DoctorReview.patient_id==goal.member_id,
        DoctorReview.status=='CONFIRMED').order_by(DoctorReview.created_at.desc())))
    result=[]
    for action in data.get('actions',[]):
        item=dict(action)
        import re
        review=next((r for r in reviews if any(action['title'] in line and '复查' in line
            and not any(word in line for word in ('无需','不需要','暂不','不建议','取消','不必'))
            for line in re.split(r'[。；;\n]',r.opinion or ''))),None)
        if item['kind']=='RECHECK':
            item['doctor_review_id']=str(review.id) if review else None
            item['operation']='建立复查安排' if review else '建立复查协调事项（核对正式医疗依据）'
        else:item['operation']='建立后续随访'
        result.append(item)
    return result


def confirm(session,goal,supervisor,*,actor,role,follow_at=None):
    from executive_health_ai.services.profile_ingestion import manager
    manager(role,actor)
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{goal.member_id})
    session.refresh(goal)
    if goal.status=='COMPLETED':return goal
    if goal.status!='WAITING_MANAGER':raise ValueError('请等待本次资料整理完成。')
    ctx=goal.context_json;p=owned(session,HealthProgram,ctx['program_id'],goal.member_id)
    actions=proposals(session,goal)
    if ctx['outcome']!='已完成' and not follow_at:
        raise ValueError('未完成事项需要明确下一次跟进日期。')
    runtime.resume(session,goal,event_type='MANAGER_RESULT_CONFIRMED',source_id=goal.id)
    goal.current_stage='回写管理记录'
    runtime.step_done(session,goal,'确认后续安排')
    source='health_event:'+ctx['event_id']
    result=supervisor.registry.execute(session,'apply_management_result',goal,{
        'program_id':str(p.id),'task_id':ctx['task_id'],'actor':actor,'result':ctx['text'],
        'outcome':ctx['outcome'],'next_action':'无需后续','follow_at':follow_at.isoformat() if follow_at else None,
        'request_key':str(goal.id),'source_reference':source,'idempotency_key':'write-result'},approved_role=role)
    goal.context_json={**goal.context_json,'log_id':result['log_id']}
    runtime.step_done(session,goal,'回写管理记录',result)
    goal.current_stage='建立后续事项'
    written=[]
    for index,action in enumerate(actions):
        due=datetime.combine(date.fromisoformat(action['date']),time(9),
            ZoneInfo(ctx.get('time_zone') or session.get(Patient,goal.member_id).timezone)).astimezone(timezone.utc)
        base={'program_id':str(p.id),'source_reference':source,'idempotency_key':'action-'+str(index)}
        if action['kind']=='RECHECK' and action.get('doctor_review_id'):
            output=supervisor.registry.execute(session,'create_recheck',goal,{**base,'data':{
                'title':action['title'],'reason':'按已确认医生意见协调复查；日期来自本次会员反馈',
                'planned_at':due.isoformat(),'owner':actor,'doctor_review_id':action['doctor_review_id'],
                'evidence':action['source_excerpt']}},approved_role=role)
        else:
            output=supervisor.registry.execute(session,'create_followup',goal,{**base,
                'title':('协调复查：' if action['kind']=='RECHECK' else '随访：')+action['title'],
                'instruction':action['source_excerpt']+'；仅协调已有计划，医学安排需核对正式依据。',
                'due_at':due.isoformat(),'owner':actor})
        written.append(output)
        from executive_health_ai.services.health_events import ingest_health_event
        kind='recheck' if 'recheck_id' in output else 'task'
        identity=output.get('recheck_id') or output['task_id']
        ingest_health_event(session,member_id=goal.member_id,event_type='TIME_DUE',event_category='TIME_DUE',
            source_type='SYSTEM',source_id=f'{kind}:{identity}:{due.isoformat()}',occurred_at=due,
            payload_ref={'work_kind':kind,'work_id':identity,'due_at':due.isoformat()},dispatch=False)
    runtime.step_done(session,goal,'建立后续事项',{'created':written})
    # Lifestyle statements remain sourced candidates, not silently overwritten
    # clinical facts. They are accessible with the original management result.
    goal.context_json={**goal.context_json,'actions_verified':True,'outputs':written,
        'confirmed_by':actor,'confirmed_at':utc_now().isoformat()}
    runtime.finish(session,goal)
    from executive_health_ai.services.care_memory import remember_result
    remember_result(session,goal)
    return goal


def manual_fallback(session,goal,*,actor,role):
    from executive_health_ai.services.profile_ingestion import manager
    from executive_health_ai.services.care_result_extraction import rules
    manager(role,actor)
    if goal.status!='FAILED':raise ValueError('当前流程不需要转人工处理。')
    parsed=rules(goal.context_json['text'],date.fromisoformat(goal.context_json['recorded_date']))
    goal.context_json={**goal.context_json,'parsed':{**parsed,'ai_used':False,
        'warning':'已转人工核对，保留原始记录与确定性识别结果。'}}
    runtime.step_done(session,goal,'整理处理结果',{'manual_fallback':True})
    goal.current_stage='确认后续安排'
    runtime.wait(session,goal,'WAITING_MANAGER',next_action='请核对原文及后续安排，确认后保存',
        expected_event='MANAGER_RESULT_CONFIRMED',expected_source=goal.id)
