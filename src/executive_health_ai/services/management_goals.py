"""Human-confirmed objectives on the existing annual program and Agent runtime."""
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select
from executive_health_ai.models import HealthProgram, HealthAssessment, ProgramPhase, AgentGoal
from executive_health_ai.models.management_workflow import IntakeAssessment
from executive_health_ai.models.goal_data import ManagementGoal
from executive_health_ai.models.base import utc_now
from executive_health_ai.services import goal_metrics, care_runtime


def intake_ready(intake):
    return bool(intake and (intake.review_status=='CONFIRMED' or
        (intake.status in {'SUBMITTED','CONFIRMED'} and
         intake.review.get('exception_intake',{}).get('confirmed_by') and
         intake.review.get('exception_intake',{}).get('completed_at'))))


def current(session, program_id):
    return session.scalar(select(ManagementGoal).where(ManagementGoal.program_id==program_id)) if program_id else None


def prerequisites(session, program):
    if not program: return {'intake':False,'goal':None,'baseline':None,'formal':False}
    year=program.cycle_year or program.start_date.year
    intake=session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==program.patient_id,
        IntakeAssessment.cycle_year==year))
    goal=current(session,program.id)
    baseline=session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id==program.patient_id,
        HealthAssessment.cycle_year==year,HealthAssessment.status.in_(('CONFIRMED','AMENDED')),
        HealthAssessment.superseded_by_id.is_(None)).order_by(HealthAssessment.version.desc()).limit(1))
    ready=intake_ready(intake)
    return {'intake':ready,'goal':goal,'baseline':baseline,
        'formal':bool(ready and baseline and goal and goal.confirmed_at and goal.plan_confirmed_at)}


def prepare(session, program, *, expression=None):
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{program.patient_id})
    existing=current(session,program.id)
    if existing:return existing
    if not prerequisites(session,program)['intake']:raise ValueError('先完成初评确认。')
    intake=session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==program.patient_id,
        IntakeAssessment.cycle_year==(program.cycle_year or program.start_date.year)))
    text=(expression or intake.member_concern or program.main_goal or '确认本年度健康管理重点').strip()
    kind=next((kind for word,kind in (('减重','WEIGHT_MANAGEMENT'),('体重','WEIGHT_MANAGEMENT'),
        ('血压','BLOOD_PRESSURE_MANAGEMENT'),('血糖','GLUCOSE_MANAGEMENT'),('血脂','LIPID_MANAGEMENT'),
        ('睡眠','SLEEP_MANAGEMENT'),('活动','ACTIVITY_MANAGEMENT'),('生活方式','LIFESTYLE_MANAGEMENT'),
        ('随访','FOLLOWUP_MANAGEMENT')) if word in text),'CUSTOM')
    if re.search(r'减\s*\d+(?:\.\d+)?\s*(?:kg|公斤|千克)',text,re.I):kind='WEIGHT_MANAGEMENT'
    metrics=goal_metrics.requirements(kind)
    primary=metrics[0].metric_code if metrics else None
    ready=goal_metrics.completeness(session,program.patient_id,kind)
    baseline=ready['latest'].get(primary,{}).get('value')
    delta=re.search(r'减(?:重)?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|千克)',text,re.I)
    target=Decimal(baseline)-Decimal(delta[1]) if delta and baseline and kind=='WEIGHT_MANAGEMENT' else None
    start=max(program.start_date,date.today())
    if program.end_date and start>program.end_date:start=program.start_date
    months=re.search(r'(\d+)\s*个月',text)
    end=min(program.end_date or start+timedelta(days=365),start+timedelta(days=30*int(months[1]) if months else 90))
    goal=ManagementGoal(patient_id=program.patient_id,program_id=program.id,goal_type=kind,title=text[:200],
        description=text,metric_code=primary,target_value=target,target_unit=goal_metrics.REGISTRY[primary].default_unit if primary else None,
        baseline_value=Decimal(baseline) if baseline else None,start_date=start,target_date=end,
        owner_id=program.owner,source='MEMBER_EXPRESSION' if expression or intake.member_concern else 'EXISTING_PROGRAM',
        requirements_json=goal_metrics.snapshot(kind))
    session.add(goal);session.flush()
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    agent=care_runtime.start(session,HealthOpsAgentSupervisor(),member_id=program.patient_id,
        kind='MANAGEMENT_SETUP',source_id=goal.id,title='确认健康管理目标',
        context={'program_id':str(program.id),'management_goal_id':str(goal.id)},owner=program.owner)
    goal.agent_goal_id=agent.id
    care_runtime.wait(session,agent,'WAITING_MANAGER',next_action='确认当前管理目标与指标',
        expected_event='MANAGEMENT_GOAL_CONFIRMED',expected_source=goal.id)
    from executive_health_ai.services.member_agents import synchronize
    synchronize(session,program.patient_id)
    return goal


def confirm_goal(session, goal, *, actor, role, title=None, goal_type=None, target=None, target_date=None):
    if role not in {'HEALTH_MANAGER','ADMIN'} or not actor.strip():raise PermissionError('目标必须由健管确认。')
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{goal.patient_id});session.refresh(goal)
    if goal.confirmed_at:return goal
    if not prerequisites(session,session.get(HealthProgram,goal.program_id))['intake']:raise ValueError('初评尚未确认。')
    if goal_type and goal_type!=goal.goal_type:
        goal.goal_type=goal_type;goal.requirements_json=goal_metrics.snapshot(goal_type)
        rules=goal_metrics.requirements(goal_type);goal.metric_code=rules[0].metric_code if rules else None
        goal.target_value=None;goal.baseline_value=None
        goal.target_unit=goal_metrics.REGISTRY[goal.metric_code].default_unit if goal.metric_code else None
    if title is not None:
        if not title.strip():raise ValueError('请填写管理目标。')
        goal.title=title.strip()
    if target=='':goal.target_value=None
    elif target is not None:
        value=Decimal(str(target))
        if not value.is_finite() or not goal.metric_code:raise ValueError('目标值无效。')
        goal.target_value=value
    if target_date is not None:goal.target_date=target_date
    if goal.target_value is not None:
        from executive_health_ai.integrations.normalization import quality_for
        if quality_for(goal_metrics.REGISTRY[goal.metric_code],goal.target_value)[0]=='invalid':
            raise ValueError('目标数值超出此指标支持的数据范围，请核对单位和目标。')
    program=session.get(HealthProgram,goal.program_id)
    if goal.target_date<goal.start_date or (program.end_date and goal.target_date>program.end_date):
        raise ValueError('目标周期须在当前年度服务周期内。')
    goal.confirmed_by,goal.confirmed_at,goal.status=actor,utc_now(),'CONFIRMED'
    program.main_goal=goal.title
    _emit(session,goal,'MANAGEMENT_GOAL_CONFIRMED',actor)
    return goal


def plan_draft(session, goal):
    existing=list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id==goal.program_id).order_by(ProgramPhase.sequence)))
    if existing:
        phases=[{'title':p.title,'start':str(p.start_date),'end':str(p.end_date),'existing_id':str(p.id)} for p in existing]
    else:
        length=(goal.target_date-goal.start_date).days+1
        count=min(3,length)
        phases=[]
        for i,title in enumerate(('建立生活方式与指标基线','稳定执行与服务跟进','目标评估与阶段复盘')[:count]):
            start=goal.start_date+timedelta(days=length*i//count)
            end=goal.start_date+timedelta(days=length*(i+1)//count-1)
            phases.append({'title':title,'start':str(start),'end':str(end)})
    baseline=prerequisites(session,session.get(HealthProgram,goal.program_id))['baseline']
    return {'template':'annual-management-v1','goal':goal.title,'phases':phases,
        'basis':{'annual_baseline_id':str(baseline.id) if baseline else None,
            'requirements_version':goal.requirements_version,
            'existing_data':goal_metrics.completeness(session,goal.patient_id,goal.goal_type,configured=goal.requirements_json)['latest']},
        'monitoring':[r.metric_code for r in goal_metrics.requirements(goal.goal_type) if r.importance=='CORE'],
        'frequency':'沿用已确认的服务周期；未配置医学监测频率',
        'actions':[{'title':'确认目标相关数据和生活方式基线','due':str(goal.start_date),
                    'instruction':'核对已有依据；核心缺失提示，辅助缺失下次补充，可选缺失不阻塞。'}]}


def confirm_plan(session,goal,*,actor,role):
    if role not in {'HEALTH_MANAGER','ADMIN'} or not actor.strip():raise PermissionError('计划必须由健管确认。')
    from executive_health_ai.models.archive_guard import locked_members
    locked_members(session.connection(),{goal.patient_id});session.refresh(goal)
    if goal.plan_confirmed_at:return goal
    if not goal.confirmed_at:raise ValueError('先确认目标。')
    if not prerequisites(session,session.get(HealthProgram,goal.program_id))['baseline']:raise ValueError('先确认年度健康基线。')
    if not goal.plan_draft:raise ValueError('计划草稿尚未准备好。')
    goal.plan_confirmed_by,goal.plan_confirmed_at=actor,utc_now()
    _emit(session,goal,'MANAGEMENT_PLAN_CONFIRMED',actor)
    return goal


def _emit(session,goal,kind,actor):
    from executive_health_ai.services.health_events import ingest_health_event
    session.flush()
    ingest_health_event(session,member_id=goal.patient_id,event_type=kind,event_category='NEW_INFORMATION',
        source_type='SYSTEM',source_id=str(goal.id),payload_ref={'actor':actor})


def on_confirmation(session,event,supervisor):
    from uuid import UUID
    goal=session.get(ManagementGoal,UUID(event.source_id))
    if not goal or goal.patient_id!=event.member_id:raise ValueError('目标不属于此会员。')
    agent=session.get(AgentGoal,goal.agent_goal_id)
    if not agent or agent.member_id!=goal.patient_id:raise ValueError('缺少原目标流程。')
    if event.event_type=='MANAGEMENT_GOAL_CONFIRMED':
        if not goal.confirmed_at or not goal.confirmed_by:raise PermissionError('目标没有人确认。')
        care_runtime.resume(session,agent,event_type=event.event_type,source_id=goal.id)
        care_runtime.step_done(session,agent,'确认管理目标')
        goal.plan_draft=plan_draft(session,goal)
        care_runtime.wait(session,agent,'WAITING_MANAGER',next_action='确认当前管理计划',
            expected_event='MANAGEMENT_PLAN_CONFIRMED',expected_source=goal.id)
        agent.current_stage='确认管理计划'
    else:
        if not goal.plan_confirmed_at or not goal.plan_confirmed_by:raise PermissionError('计划没有人确认。')
        care_runtime.resume(session,agent,event_type=event.event_type,source_id=goal.id)
        care_runtime.step_done(session,agent,'确认管理计划')
        from executive_health_ai.services.management_workflow import ManagementWorkflowService
        service=ManagementWorkflowService();program=session.get(HealthProgram,goal.program_id)
        phases=list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id==program.id).order_by(ProgramPhase.sequence)))
        if not phases:
            for draft in goal.plan_draft['phases']:
                phases.append(service.add_phase(session,goal.patient_id,program.id,title=draft['title'],
                    goal=goal.title,content='跟踪已确认目标指标；按已有业务模板执行',
                    start=date.fromisoformat(draft['start']),end=date.fromisoformat(draft['end']),owner=goal.owner_id))
        if not any(p.status=='ACTIVE' for p in phases):phases[0].status='ACTIVE'
        program.status='ACTIVE';program.current_phase=next(p.phase_code for p in phases if p.status=='ACTIVE')
        refs=[]
        for index,action in enumerate(goal.plan_draft['actions']):
            result=supervisor.registry.execute(session,'create_management_item',agent,{
                'program_id':str(program.id),'title':action['title'],'instruction':action['instruction'],
                'owner':goal.owner_id,'due_at':datetime.combine(date.fromisoformat(action['due']),time(9),tzinfo=timezone.utc).isoformat(),
                'idempotency_key':f'goal-plan:{goal.id}:{index}','source_reference':str(goal.id)},approved_role='HEALTH_MANAGER')
            refs.append(result['task_id'])
        goal.status='ACTIVE'
        logged=supervisor.registry.execute(session,'write_management_log',agent,{
            'program_id':str(program.id),'source_reference':str(goal.id),'idempotency_key':'goal-plan-log:'+str(goal.id),
            'data':{'category':'数据跟进','channel':'系统记录','member_issue':goal.title,
                'manager_action':'健管已分别确认目标与管理计划','result':f'已建立或复用 {len(phases)} 个阶段，落实 {len(refs)} 项管理工作',
                'next_action':goal.plan_draft['actions'][0]['title'],'owner':goal.owner_id}},approved_role='HEALTH_MANAGER')
        agent.context_json={**agent.context_json,'work_refs':refs,'log_id':logged['log_id'],'actions_verified':True}
        care_runtime.finish(session,agent)
    return agent


def prepare_for_intake(session,intake):
    if not intake_ready(intake):return None
    from executive_health_ai.services.member_management_projection import intake_program
    program=intake_program(session,intake)
    return prepare(session,program) if program else None
