"""One bounded intake policy using the existing supervisor and tool registry."""
from uuid import UUID
from sqlalchemy import select, update
from executive_health_ai.models import AgentGoal, AgentPlanStep, AgentApprovalRequest, AgentRunTrace, DoctorReview, Document
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.profile_ingestion import ProfileIngestionService, candidates, manager
from executive_health_ai.services.responsibility import ResponsibilityRouter
from executive_health_ai.agent.care_routing import latest, record

STAGES=('RECEIVED','PARSING','NORMALIZING','MATCHING','REVIEW','WRITING')
LABELS=dict(zip(STAGES,('资料接收','资料解析','字段标准化','档案匹配','健管确认','写入档案')))


def is_profile_goal(goal):
    return bool(goal and goal.goal_type=='PROFILE_INTAKE')


def trace(session,goal,text,action='profile_activity',tool_name=None,**metadata):
    session.add(AgentRunTrace(goal_id=goal.id,plan_id=goal.current_plan_id,action=action,
        status='FAILED' if action=='profile_exception' else 'COMPLETED',tool_name=tool_name,
        result_summary=text,completed_at=utc_now(),metadata_json=metadata))
    session.flush()


def route(session,goal,code,actor=None,cleared=False):
    review=session.get(DoctorReview,UUID(goal.context_json['review_id'])) if goal.context_json.get('review_id') else None
    decision=ResponsibilityRouter().decide(reason_codes=[code],previous=latest(session,goal),
        evidence_refs=['document:'+goal.source_id],confirmed_by=actor,
        doctor_cleared=bool(review and review.status=='CONFIRMED'),escalation_cleared=cleared)
    record(session,goal,decision)
    return decision


def handle_event(supervisor,session,event):
    if event.event_type=='HEALTH_DOCUMENT_UPLOADED':
        goal=session.scalar(select(AgentGoal).where(AgentGoal.goal_type=='PROFILE_INTAKE',AgentGoal.source_id==event.source_id))
        if not goal:
            doc=session.get(Document,UUID(event.source_id))
            if not doc or doc.patient_id!=event.member_id: raise ValueError('资料不属于此会员。')
            goal=AgentGoal(member_id=event.member_id,goal_type='PROFILE_INTAKE',title='完成本次健康资料解析与档案更新准备',
                source_type='health_document',source_id=event.source_id,status='RUNNING',current_stage='RECEIVED',
                owner=event.metadata_json['uploaded_by'],created_by=event.metadata_json['uploaded_by'],
                next_action='正在读取上传资料',context_json=dict(event.metadata_json),success_criteria={})
            if event.metadata_json.get('intake_id'):
                goal.title='整理本份资料并辅助完成初始健康评估'
            session.add(goal);session.flush()
            supervisor.planner.create_plan(session,goal,reason='收到健康资料后准备档案更新')
            trace(session,goal,'已接收'+doc.title,event_id=str(event.id))
            route(session,goal,'NON_MEDICAL_PREPARATION')
        event.status,event.processed_at='PROCESSED',utc_now()
        return True,goal
    if event.event_type=='DOCTOR_REVIEW_COMPLETED':
        for goal in session.scalars(select(AgentGoal).where(AgentGoal.goal_type=='PROFILE_INTAKE',AgentGoal.status=='WAITING_DOCTOR')):
            if goal.context_json.get('review_id')!=event.source_id: continue
            review=session.get(DoctorReview,UUID(event.source_id))
            if review and review.patient_id==goal.member_id and review.status=='CONFIRMED':
                goal.status,goal.current_stage,goal.next_action='WAITING_MANAGER','REVIEW','医生意见已返回，请确认档案更新'
                trace(session,goal,'已收到医生判断，继续等待健管确认档案更新')
                route(session,goal,'PROFILE_CONFIRMATION')
                event.status,event.processed_at='PROCESSED',utc_now()
                return True,goal
    return False,None


def register_tools(registry):
    from executive_health_ai.agent.tools import AgentTool, AUTO, MANAGER_APPROVAL
    registry.register(AgentTool('parse_profile_document','整理健康资料候选',AUTO,'write',True,120,
        lambda s,g,c:ProfileIngestionService().parse(s,g)))
    registry.register(AgentTool('match_profile_document','匹配已有档案并预填草稿',AUTO,'write',True,30,
        lambda s,g,c:ProfileIngestionService().match(s,g)))
    registry.register(AgentTool('approve_profile_document','写入已确认档案资料',MANAGER_APPROVAL,'write',True,60,
        lambda s,g,c:ProfileIngestionService().approve(s,g,c['decisions'],actor=c['actor'],role=c['role'])))
    registry.register(AgentTool('request_profile_review','汇总资料提交医学判断',MANAGER_APPROVAL,'write',True,30,
        lambda s,g,c:{'review_id':str(ProfileIngestionService().request_review(s,g,c['question'],c['actor']).id)}))


def advance(supervisor,session,goal,*,claimed=False):
    if goal.status!=('PROCESSING' if claimed else 'RUNNING') or goal.automation_paused: return goal
    stage=goal.current_stage
    # Compare-and-set prevents browser refresh and worker from executing the
    # same step concurrently. Transaction rollback restores the claim on error.
    claimed=claimed or session.execute(update(AgentGoal).where(AgentGoal.id==goal.id,AgentGoal.status=='RUNNING',
        AgentGoal.current_stage==stage).values(status='PROCESSING'),execution_options={'synchronize_session':False}).rowcount
    if not claimed:return goal
    session.refresh(goal)
    step=session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id,AgentPlanStep.step_type==stage))
    try:
        if stage=='RECEIVED':
            text='已保存原始资料，准备读取内容';following='PARSING'
        elif stage=='PARSING':
            result=supervisor.registry.execute(session,'parse_profile_document',goal)
            text=f"已提取 {result['count']} 项有来源的健康信息";following='NORMALIZING'
        elif stage=='NORMALIZING':
            rows=candidates(session,goal)
            text=f"已匹配 {sum(bool(r.canonical_code) for r in rows)} 项标准健康指标；其余资料按档案字段整理";following='MATCHING'
        elif stage=='MATCHING':
            result=supervisor.registry.execute(session,'match_profile_document',goal)
            from executive_health_ai.services.daily_summary import current_goal
            from executive_health_ai.services.goal_metrics import completeness
            objective=current_goal(session,goal.member_id)
            if objective:
                ready=completeness(session,goal.member_id,objective.goal_type,configured=objective.requirements_json)
                required={r['metric_code'] for r in objective.requirements_json}
                goal.context_json={**goal.context_json,'goal_data':{'management_goal_id':str(objective.id),
                    'title':objective.title,'readiness':ready,
                    'document_metric_candidates':[{'metric':r.canonical_code,'candidate_id':str(r.id)}
                        for r in candidates(session,goal) if r.canonical_code in required],
                    'candidate_policy':'候选不计入正式完整度，可靠依据经原治理流程入档后再计算'}}
            text=f"已核对现有档案，发现 {result['conflicts']} 项冲突";following='REVIEW'
        else: raise ValueError('流程需要健管确认后继续。')
        step.started_at=step.started_at or utc_now()
        step.status,step.completed_at,step.result_summary='COMPLETED',utc_now(),text
        trace(session,goal,text,tool_name={'PARSING':'parse_profile_document','MATCHING':'match_profile_document'}.get(stage))
        goal.current_stage=following
        goal.status='WAITING_MANAGER' if following=='REVIEW' else 'RUNNING'
        goal.next_action='确认档案更新；有冲突的资料须逐项选择' if following=='REVIEW' else '正在'+LABELS[following]
        if following=='REVIEW' and goal.context_json.get('intake_id'):
            goal.next_action='在健康档案处理待确认、冲突和缺失资料，再确认提交初评'
        if following=='REVIEW':
            waiting=session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id==goal.current_plan_id,AgentPlanStep.step_type=='REVIEW'))
            waiting.status='WAITING_MANAGER'
            supervisor._approval(session,goal,waiting,'PROFILE_INTAKE','HEALTH_MANAGER')
            route(session,goal,'PROFILE_CONFIRMATION')
    except (ValueError,OSError) as exc:
        goal.status,goal.next_action='ESCALATED',str(exc)
        step.status,step.error_summary='FAILED',str(exc)
        trace(session,goal,str(exc),'profile_exception',tool_name={'PARSING':'parse_profile_document','MATCHING':'match_profile_document'}.get(stage))
        route(session,goal,'UNREADABLE_REPORT')
    session.flush()
    return goal


def confirm(supervisor,session,goal,decisions,*,actor,role):
    manager(role,actor)
    if goal.status=='COMPLETED':return goal
    if goal.context_json.get('intake_id'):
        raise ValueError('本次资料用于初评草稿，请回到初始评估核对各步骤后提交。')
    if not is_profile_goal(goal) or goal.status!='WAITING_MANAGER':raise ValueError('当前尚不能确认写入。')
    responsibility=latest(session,goal)
    if responsibility and responsibility.route_type in {'DOCTOR','ESCALATE'}:raise ValueError('请先完成医生判断或人工处理。')
    claimed=session.execute(update(AgentGoal).where(AgentGoal.id==goal.id,AgentGoal.status=='WAITING_MANAGER')
        .values(status='WRITING'),execution_options={'synchronize_session':False}).rowcount
    if not claimed:raise ValueError('此确认已在处理，请刷新查看结果。')
    session.refresh(goal)
    counts=supervisor.registry.execute(session,'approve_profile_document',goal,{'decisions':decisions,'actor':actor,'role':role},approved_role=role)
    for approval in session.scalars(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id==goal.id,AgentApprovalRequest.status=='PENDING')):
        approval.status,approval.decided_by,approval.decided_at,approval.decision='APPROVED',actor,utc_now(),'APPROVE'
    for step in supervisor.planner.steps(session,goal.current_plan_id):
        step.status='COMPLETED';step.completed_at=step.completed_at or utc_now()
    goal.context_json={**goal.context_json,'output':counts,'next_node':'核对待补充资料（明天）' if counts['deferred'] else '查看健康档案；继续完成初始评估中的未填部分'}
    goal.success_criteria={'parsed':True,'reviewed':True,'conflicts_resolved_or_deferred':True,'facts_written':True,'shared_projection':True,'next_node':True}
    goal.status,goal.current_stage,goal.completed_at='COMPLETED','WRITING',utc_now()
    goal.next_action=goal.context_json['next_node']
    trace(session,goal,'已按健管确认写入档案，会员360与成员端读取同一份正式记录',tool_name='approve_profile_document')
    route(session,goal,'CONFIRMED_ARRANGEMENTS',actor)
    return goal


def retry(session,goal,*,actor,role):
    manager(role,actor)
    if goal.status!='ESCALATED': raise ValueError('此流程无需重新解析。')
    # Retry only failed parsing. A medical hold can never be cleared here.
    if goal.context_json.get('review_id'): raise ValueError('需先完成医生判断。')
    from executive_health_ai.models import ReportExtractionRun
    run=session.get(ReportExtractionRun,UUID(goal.context_json['run_id']))
    if candidates(session,goal): raise ValueError('已识别部分资料，请先人工核对；如需重新解析请上传修订文件。')
    run.status='PENDING'
    goal.status,goal.current_stage,goal.next_action='RUNNING','PARSING','正在重新读取原文件'
    route(session,goal,'NON_MEDICAL_PREPARATION',actor,cleared=True)
    trace(session,goal,'健管已申请重新读取原文件')


def request_doctor(session,goal,*,question,actor,role):
    manager(role,actor)
    if goal.status!='WAITING_MANAGER' or not question.strip():raise ValueError('请填写明确需要医生判断的问题。')
    if goal.context_json.get('review_id'):raise ValueError('此流程已有关联医生判断，请查看原记录。')
    # The service owns DoctorReview and its required administrative question
    # record; that pending question is excluded from the formal member archive.
    from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
    result=HealthOpsAgentSupervisor().registry.execute(session,'request_profile_review',goal,
        {'question':question,'actor':actor},approved_role=role)
    review=session.get(DoctorReview,UUID(result['review_id']))
    goal.context_json={**goal.context_json,'review_id':str(review.id)}
    goal.status,goal.next_action='WAITING_DOCTOR','医生提交后自动继续，由健管确认档案更新'
    route(session,goal,'MANAGER_REQUEST',actor)
    trace(session,goal,'已汇总原始资料并提交医生判断',tool_name='request_profile_review')
    return review
