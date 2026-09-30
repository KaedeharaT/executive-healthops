"""One confirmed archive transaction; no physical deletion or medical conclusions."""
from sqlalchemy import select
from executive_health_ai.models import (Patient, AuditLog, AgentGoal, AgentPlan, AgentPlanStep,
    AgentApprovalRequest, AgentRunTrace, AgentEvent, Task, ServiceRequest, HealthProgram,
    ProgramPhase, HealthJourney, FollowUp, ManagementPlan, CarePlan, CareTask, DoctorReview, MemberAgent, HealthEvent)
from executive_health_ai.models.management_workflow import RecheckPlan, ConsultationCase
from executive_health_ai.models.base import utc_now
from executive_health_ai.models.archive_guard import locked_members

CLOSED={'COMPLETED','CANCELLED','CLOSED','REVIEWED','REJECTED','CONFIRMED','FAILED'}
REASON='因成员归档停止；未标记为完成，历史资料保留。'


def active_ids():
    return select(Patient.id).where(Patient.archived_at.is_(None))


def member_label(member):
    return member.display_name or member.external_id or '会员·'+str(member.id)[:8]


def require_active(session, member_id):
    row=session.execute(select(Patient.id,Patient.archived_at).where(Patient.id==member_id)).first()
    if not row or row.archived_at is not None:
        raise ValueError('成员不存在或已归档，不能继续执行工作。')


def is_archived(session, member_id):
    return session.scalar(select(Patient.archived_at).where(Patient.id==member_id)) is not None


class MemberArchiveService:
    def is_running(self,session,member_id):
        return bool(session.scalar(select(MemberAgent.id).where(MemberAgent.member_id==member_id,MemberAgent.status=='RUNNING'))
            or session.scalar(select(AgentGoal.id).where(AgentGoal.member_id==member_id,AgentGoal.status.in_({'RUNNING','PROCESSING','WRITING','ACTIVE'}))))

    def preview(self,session,member_id):
        return {label:len(list(session.scalars(select(model).where(column==member_id,model.status.not_in(CLOSED)))))
            for label,model,column in [('自动化流程',AgentGoal,AgentGoal.member_id),('未完成事项',Task,Task.patient_id),
                ('未完成复查',RecheckPlan,RecheckPlan.patient_id),('进行中服务',ServiceRequest,ServiceRequest.patient_id),
                ('等待医生',DoctorReview,DoctorReview.patient_id),('未完成会诊',ConsultationCase,ConsultationCase.patient_id)]}

    def archive(self,session,member_id,*,expected_name,confirmation_name,actor,role,confirmed=False,stop_running=False):
        if role not in {'HEALTH_MANAGER','ADMIN'} or not actor.strip():
            raise PermissionError('仅健康管理师或管理员可以归档成员。')
        if not confirmed or not confirmation_name.strip() or confirmation_name!=expected_name:
            raise ValueError('请输入完全一致的会员姓名并确认归档。')
        states=locked_members(session.connection(),{member_id})
        if member_id not in states:
            raise ValueError('成员不存在。')
        member=session.get(Patient,member_id,populate_existing=True)
        if member_label(member)!=expected_name:
            raise ValueError('会员姓名已变化，请取消后重新核对要归档的会员。')
        if member.archived_at:
            return member
        if self.is_running(session,member_id) and not stop_running:
            raise ValueError('该会员当前仍有自动化流程正在运行。请取消，或明确选择停止当前流程并归档。')
        session.info['archiving_member']=member_id
        try:
            now=utc_now();impact=self.preview(session,member_id);changes=[]
            def stop(row,status):
                changes.append({'type':type(row).__name__,'id':str(row.id),'from':row.status,'to':status})
                row.status=status
            goals=list(session.scalars(select(AgentGoal).where(AgentGoal.member_id==member_id)))
            for goal in goals:
                if goal.status in {'COMPLETED','CANCELLED'}:
                    continue
                previous=goal.status
                stop(goal,'CANCELLED')
                goal.automation_paused=True;goal.next_check_at=None
                goal.takeover_by=actor;goal.takeover_reason=REASON;goal.next_action=REASON
                # The success criteria, clinical context, and completion timestamp remain intact.
                plans=list(session.scalars(select(AgentPlan).where(AgentPlan.goal_id==goal.id)))
                for plan in plans:
                    if plan.status=='ACTIVE':stop(plan,'CANCELLED')
                    for step in session.scalars(select(AgentPlanStep).where(AgentPlanStep.plan_id==plan.id)):
                        if step.status not in {'COMPLETED','SKIPPED','CANCELLED'}:
                            stop(step,'CANCELLED');step.next_retry_at=None;step.scheduled_for=None
                for approval in session.scalars(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id==goal.id,AgentApprovalRequest.status=='PENDING')):
                    stop(approval,'CANCELLED');approval.decision='CANCELLED';approval.decided_by=actor
                    approval.decided_at=now;approval.comment=REASON
                session.add(AgentRunTrace(goal_id=goal.id,plan_id=goal.current_plan_id,action='member_archived',
                    status='CANCELLED',started_at=now,completed_at=now,result_summary=REASON,
                    metadata_json={'previous_status':previous,'actor':actor,'reason':'MEMBER_ARCHIVED'}))
            for event in session.scalars(select(AgentEvent).where(AgentEvent.member_id==member_id,AgentEvent.status=='PENDING')):
                stop(event,'CANCELLED');event.processed_at=now
                event.metadata_json={**(event.metadata_json or {}),'stop_reason':'MEMBER_ARCHIVED'}
            for event in session.scalars(select(HealthEvent).where(HealthEvent.member_id==member_id,
                    HealthEvent.event_category.is_not(None),HealthEvent.status=='PENDING')):
                stop(event,'IGNORED');event.route_action='IGNORE'
            identity=session.scalar(select(MemberAgent).where(MemberAgent.member_id==member_id))
            if identity:
                stop(identity,'IDLE')
                identity.current_goal_id=None;identity.waiting_for=None;identity.next_wake_at=None
            for model in (Task,FollowUp,RecheckPlan,ServiceRequest,CareTask):
                for row in session.scalars(select(model).where(model.patient_id==member_id)):
                    # Recheck COMPLETED means the examination was performed but
                    # its report/review is still pending; only CLOSED is final.
                    terminal = {'CLOSED','CANCELLED'} if model is RecheckPlan else {'COMPLETED','CANCELLED','CLOSED','FAILED','REJECTED'}
                    if row.status.upper() not in terminal:
                        stop(row,'cancelled' if model is CareTask else 'CANCELLED')
                        if model is ServiceRequest:
                            row.next_action='成员已归档；负责人需人工核对外部预约与费用，不代表外部服务已撤销。'
                        if model is RecheckPlan:row.next_recheck_at=None
            for model in (HealthProgram,HealthJourney,ManagementPlan,CarePlan):
                for row in session.scalars(select(model).where(model.patient_id==member_id)):
                    if row.status.upper() not in CLOSED | {'PAUSED'}:stop(row,'paused' if model is CarePlan else 'PAUSED')
                    if model is HealthProgram:
                        for phase in session.scalars(select(ProgramPhase).where(ProgramPhase.program_id==row.id)):
                            if phase.status not in CLOSED | {'PAUSED'}:stop(phase,'PAUSED')
            # Pending DoctorReview/Consultation and Risk remain truthful unresolved records.
            member.archived_at=now
            session.add(AuditLog(patient_id=member_id,actor=actor,actor_role=role.lower(),action='member_archived',
                entity_type='Patient',entity_id=str(member_id),detail_json={'strategy':'ARCHIVE','reason':REASON,
                    'impact':impact,'changes':changes,'medical_handoff':'待医生判断、会诊及未解决风险保留；归档不等于医学问题已解决。'}))
            session.flush()
            return member
        finally:
            session.info.pop('archiving_member',None)
