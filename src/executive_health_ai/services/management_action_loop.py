"""Resolve human work and compose existing commands; no second workflow store."""
from dataclasses import dataclass
from datetime import date,datetime,time,timedelta,timezone
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import Task,HealthProgram,ProgramPhase,DoctorReview,ServiceRequest
from executive_health_ai.models.management_workflow import ManagementLog,StageReview
from executive_health_ai.models.base import utc_now
from executive_health_ai.services.management_workflow import ManagementWorkflowService,owned,required
from executive_health_ai.services.member_management_projection import MemberManagementProjection
from executive_health_ai.services.task_transitions import TaskTransitionService
from executive_health_ai.services.member_archive import require_active

CLOSED={'COMPLETED','CANCELLED','CLOSED','CONFIRMED','REJECTED'}

@dataclass(frozen=True)
class Work:
    id: str
    kind: str
    record: object
    title: str
    reason: str
    owner: str
    due: object
    status: str
    source: str
    next_action: str


def in_phase(row,phase):
    at=getattr(row,'due_at',None) or getattr(row,'planned_at',None) or getattr(row,'scheduled_at',None)
    return bool(phase and (getattr(row,'phase_id',None)==phase.id or
        getattr(row,'program_id',None)==phase.program_id and (not at or phase.start_date<=at.date()<=phase.end_date)))


class ManagementActionLoop:
    def project(self,session,member_id,program_id=None):
        view=MemberManagementProjection().member(session,member_id,program_id)
        phase=view.current_phase;items=[]
        linked={r.management_task_id for r in view.services if r.management_task_id and r.status not in CLOSED}
        def add(kind,row,title,reason,owner,due,source,cta):
            items.append(Work(kind+':'+str(row.id),kind,row,title,reason,owner or view.owner,due,row.status,source,cta))
        for task in view.tasks:
            if task.status in CLOSED or task.id in linked:continue
            handoff=any(phase and r.phase_id==phase.id and task.source==f'stage_result:{r.id}' for r in view.reviews)
            kind='RISK' if task.risk_event_id else 'DOCTOR' if task.responsible_role=='doctor' else 'STAGE_REVIEW' if handoff else 'FOLLOWUP' if task.source.startswith(('management_log:','followup:','service_result:')) or '随访' in task.title else 'MANAGEMENT'
            add(kind,task,task.title,task.instruction,task.assignee,task.due_at,'正式风险工作流' if kind=='RISK' else '管理日志后续' if task.source.startswith('management_log:') else '管理计划','进入风险工作流' if kind=='RISK' else '记录随访结果' if kind=='FOLLOWUP' else '填写处理结果')
        for row in view.rechecks:
            if row.status!='CLOSED':add('RECHECK',row,row.title,row.reason,row.owner,row.planned_at,'检查复查计划','推进复查状态')
        for row in view.services:
            if row.status not in CLOSED:add('SERVICE',row,row.reason,'按已申请服务推进审核、安排、执行与结果回写',row.assigned_manager,row.scheduled_at or row.sla_due_at,'服务申请',row.next_action or '处理服务安排')
        for row in view.doctor_reviews:
            if row.status=='PENDING':add('DOCTOR',row,row.question_for_doctor,row.doctor_brief,row.doctor_name,None,'医生协同','查看医学问题 / 等待医生')
        now=utc_now()
        def priority(item):
            at=item.due or datetime.max.replace(tzinfo=timezone.utc)
            urgent= item.kind=='RISK' and getattr(item.record,'priority','') in {'HIGH','URGENT'}
            return (not urgent,at>now, {'HIGH':0,'MEDIUM':1,'LOW':2}.get(getattr(item.record,'priority','MEDIUM'),1),at,item.id)
        items.sort(key=priority)
        review=next((r for r in view.reviews if phase and r.phase_id==phase.id),None)
        def belongs(row):
            return in_phase(row,phase) or any(getattr(row,'source','')==f'service_result:{r.id}' and in_phase(r,phase) for r in view.services)
        planned=[t for t in view.tasks if belongs(t) and not t.source.startswith('stage_result:')]
        phase_open=[i for i in items if i.kind!='STAGE_REVIEW' and belongs(i.record)]
        # An empty phase is not automatically considered completed.
        has_plan=bool(planned or any(in_phase(r,phase) for r in (*view.rechecks,*view.services)))
        ready=bool(phase and not review and ((has_plan and not phase_open) or phase.end_date<=date.today()))
        all_done=bool(has_plan and not phase_open and all(t.status=='COMPLETED' for t in planned)
            and all(r.status=='COMPLETED' for r in view.services if in_phase(r,phase)))
        state='NEXT_PHASE' if review else 'STAGE_REVIEW' if ready else 'WORK' if items else 'CREATE'
        next_item=items[0] if items else None
        if phase_open:
            # The administrative handoff cannot outrank unfinished execution
            # (notably the followup created when a doctor returns a decision).
            next_item=next((i for i in items if i.kind!='STAGE_REVIEW'),None)
        if phase and (ready or review) and not phase_open:
            # Future-phase plans stay in the table, but cannot bypass the human
            # stage handoff. Urgent risks and already-due work still take priority.
            next_item=next((i for i in items if i.kind!='STAGE_REVIEW' and
                (i.kind=='DOCTOR' or i.due and i.due<=now or i.kind=='RISK' and getattr(i.record,'priority','') in {'HIGH','URGENT'})),None)
        from executive_health_ai.services.service_operations_projection import stage_evidence
        return dict(view=view,items=items,next=next_item,phase=phase,review=review,
            evidence=stage_evidence(session,member_id,view.program.id,phase) if view.program else {},
            state=state,review_ready=ready,phase_open=phase_open,planned=planned,all_done=all_done)

    def process_task(self,session,member_id,program_id,task_id,*,actor,result,outcome,next_action,follow_at,request_key):
        require_active(session,member_id)
        task=owned(session,Task,task_id,member_id);program=owned(session,HealthProgram,program_id,member_id)
        if task.program_id not in {None,program.id}:raise ValueError('事项不属于当前年度。')
        if task.risk_event_id or task.responsible_role=='doctor':raise ValueError('请进入此事项原有风险 / 医生工作流。')
        prior=session.scalar(select(ManagementLog).where(ManagementLog.request_key==request_key))
        if prior:
            if prior.patient_id!=member_id or prior.related_task_id!=task.id:raise ValueError('重复请求不属于本次事项。')
            return prior
        if task.status in CLOSED:raise ValueError('事项已结束，请重新选择下一项。')
        required(result,'处理结果')
        if outcome not in {'已完成','部分完成','未完成'}:raise ValueError('请选择结果状态。')
        if next_action not in {'继续随访','安排复查','申请服务','提交医生','无需后续'}:raise ValueError('请选择下一步。')
        if (outcome!='已完成' or next_action=='继续随访') and not follow_at:raise ValueError('请为未完成事项或继续随访填写跟进日期。')
        workflow=ManagementWorkflowService()
        log=workflow.record_log(session,member_id,program.id,actor=actor,request_key=request_key,
            occurred_at=utc_now(),category='日常跟进',channel='其他',member_issue=task.title,
            manager_action='记录本次处理：'+outcome,result=result,next_action='' if next_action=='无需后续' else next_action,
            follow_up_at=follow_at or (utc_now() if next_action!='无需后续' else None),owner=actor,related_task_id=task.id,
            create_followup=outcome=='已完成' and next_action!='无需后续')
        if outcome=='已完成':
            TaskTransitionService().complete(session,task.id,actor=actor,outcome=result)
            from executive_health_ai.services.daily_care import work_completed
            work_completed(session,member_id,task.id)
        else:
            # Retain the original open task, never turn partial work into Completed.
            task.due_at=follow_at
        return log

    def stage_summary(self,state):
        view=state['view'];phase=state['phase']
        logs=[r for r in view.logs if phase and phase.start_date<=r.occurred_at.date()<=phase.end_date]
        return {'实际完成':'；'.join(t.title for t in state['planned'] if t.status=='COMPLETED') or '尚无已完成计划事项，请核对',
            '管理日志':'；'.join(r.result for r in logs) or '本阶段暂无管理日志',
            '会员反馈与沟通':'；'.join(f'{r.occurred_at.date()} · {r.channel} · {r.member_issue}；{r.result}' for r in logs) or '暂无已记录会员反馈',
            '检查完成':'；'.join(r.title+'：'+(r.result or r.status) for r in view.rechecks if in_phase(r,phase)) or '本阶段无关联复查',
            '服务完成':'；'.join((r.result_summary or r.reason)+'：'+r.status for r in view.services if in_phase(r,phase)) or '本阶段无关联服务',
            '未解决问题':'；'.join(i.title for i in state['phase_open']) or '暂无开放阶段事项；仍需健管核对',
            **state.get('evidence', {}),
            '下一阶段建议':phase.goal if phase else '请健管制定下一阶段目标'}

    def review_stage(self,session,member_id,program_id,*,phase_id,content,actor,medical=False):
        require_active(session,member_id)
        state=self.project(session,member_id,program_id)
        if not state['phase'] or state['phase'].id!=phase_id or not state['review_ready']:raise ValueError('当前阶段尚未满足复盘条件，请刷新并核对阶段工作。')
        return ManagementWorkflowService().review_stage(session,member_id,phase_id,content=content,
            decision='DOCTOR_REVIEW' if medical else 'CONTINUE',actor=actor)

    def next_phase_draft(self,state):
        phase=state['phase'];view=state['view']
        existing=next((p for p in view.phases if phase and p.sequence>phase.sequence),None)
        review=state['review']
        return {'existing':existing,'title':existing.title if existing else '下一阶段持续管理',
            'goal':existing.goal if existing else review.content.get('下一阶段建议','') if review else '',
            'content':existing.management_content or existing.goal if existing else '落实健管已确认的阶段复盘建议；医学安排仍遵循医生意见。',
            'start':existing.start_date if existing else phase.end_date+timedelta(days=1),
            'end':existing.end_date if existing else min(phase.end_date+timedelta(days=30),view.program.end_date or phase.end_date+timedelta(days=30))}

    def enter_next_phase(self,session,member_id,program_id,phase_id,*,actor,title,goal,content,start,end,action):
        require_active(session,member_id);state=self.project(session,member_id,program_id)
        if not state['phase'] or state['phase'].id!=phase_id or not state['review']:raise ValueError('请先确认当前阶段复盘。')
        if any(r.status=='PENDING' for r in state['view'].doctor_reviews):raise ValueError('医学判断尚未完成，请等待医生。')
        if state['phase_open']:raise ValueError('仍有本阶段开放事项，请先处理或在原流程中明确安排。')
        draft=self.next_phase_draft(state);workflow=ManagementWorkflowService()
        following=draft['existing']
        if not following:following=workflow.add_phase(session,member_id,program_id,title=title,goal=goal,content=content,start=start,end=end,owner=actor)
        required(action,'下一阶段第一件管理事项')
        result=workflow.advance_phase(session,member_id,phase_id,actor)
        from executive_health_ai.services import care_commands
        care_commands.schedule_followup(session,state['view'].program,title=action,instruction=content,owner=actor,
            due_at=datetime.combine(result.start_date,time(9),timezone.utc))
        for task in state['view'].tasks:
            if task.source==f"stage_result:{state['review'].id}" and task.status not in CLOSED:
                TaskTransitionService().complete(session,task.id,actor=actor,outcome='健管已确认并进入下一阶段')
        # Complete the original stage goal only after the service has actually
        # created/activated the next phase and its first accountable action.
        from executive_health_ai.models import AgentGoal
        from executive_health_ai.services import care_runtime
        for goal_record in session.scalars(select(AgentGoal).where(AgentGoal.member_id==member_id,
                AgentGoal.goal_type=='STAGE_REVIEW',AgentGoal.source_id==str(phase_id))):
            if goal_record.status!='COMPLETED':
                goal_record.context_json={**goal_record.context_json,'review_id':str(state['review'].id),
                    'next_phase_id':str(result.id)}
                care_runtime.finish(session,goal_record)
        return result
