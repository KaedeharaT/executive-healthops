"""Read-only annual member workspace and due work, using existing sources."""
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from sqlalchemy import select, or_
from executive_health_ai.models import HealthProgram, ProgramPhase, DoctorReview, Document, HealthAssessment, Task, ServiceRequest, ClinicalRecommendation, Patient, RiskEvent
from executive_health_ai.models.management_workflow import IntakeAssessment, ManagementLog, RecheckPlan, ConsultationCase, FamilyRelation, StageReview


@dataclass(frozen=True)
class MemberManagementView:
    program: object
    programs: tuple
    intake: object
    phases: tuple
    logs: tuple
    rechecks: tuple
    consultations: tuple
    family: tuple
    reviews: tuple
    doctor_reviews: tuple
    documents: tuple
    tasks: tuple
    services: tuple
    onboarding: str
    milestones: tuple
    risks: tuple = ()

    @property
    def owner(self):
        return self.program.owner if self.program else '待分配'

    @property
    def current_phase(self):
        return next((p for p in self.phases if p.status=='ACTIVE'),None)


class MemberManagementProjection:
    def member(self,session,member_id,program_id=None):
        programs=tuple(session.scalars(select(HealthProgram).where(HealthProgram.patient_id==member_id).order_by(HealthProgram.created_at.desc())))
        from executive_health_ai.services.product_projection import current_program
        program=next((p for p in programs if p.id==program_id),None) if program_id else current_program(programs)
        if not program and programs: program=programs[0]
        year=program.cycle_year or program.start_date.year if program else datetime.now().year
        intake=session.scalar(select(IntakeAssessment).where(IntakeAssessment.patient_id==member_id,IntakeAssessment.cycle_year==year))
        phases=tuple(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id==program.id).order_by(ProgramPhase.sequence))) if program else ()
        def rows(model,order):
            query=select(model).where(model.patient_id==member_id)
            if hasattr(model,'program_id') and program:
                if model in {DoctorReview, Task, ServiceRequest, ConsultationCase}:
                    query=query.where(or_(model.program_id==program.id,model.program_id.is_(None)))
                else:
                    query=query.where(model.program_id==program.id)
            return tuple(session.scalars(query.order_by(order)))
        docs=rows(Document,Document.created_at.desc())
        baseline=session.scalar(select(HealthAssessment).where(HealthAssessment.patient_id==member_id,HealthAssessment.cycle_year==year,HealthAssessment.status=='CONFIRMED'))
        medical=not intake or not intake.doctor_review_id or (session.get(DoctorReview,intake.doctor_review_id).status=='CONFIRMED')
        milestones=(('基础资料', bool(intake and '基础资料' in intake.responses)),
            ('初始问卷',bool(intake and intake.status!='DRAFT')),('报告收集',bool(docs)),
            ('健管初评',bool(intake and intake.review_status=='CONFIRMED')),('医学确认（按需）',medical),
            ('健康基线',bool(baseline)),('年度方案',bool(program and program.status=='ACTIVE' and phases)))
        if not program: state='待建档'
        elif not intake or intake.status=='DRAFT': state='资料收集中'
        elif intake.review_status=='WAITING_MEDICAL_REVIEW': state='待医学确认'
        elif intake.review_status!='CONFIRMED': state='待健管初评'
        elif not baseline: state='待建立基线'
        elif not phases or program.status=='PLANNED': state='待制定方案'
        else: state='持续管理中'
        rechecks=rows(RecheckPlan,RecheckPlan.planned_at)
        if intake and intake.review_status=='CONFIRMED' and not baseline and any(r.status!='CLOSED' for r in rechecks): state='待补充检查'
        return MemberManagementView(program,programs,intake,phases,rows(ManagementLog,ManagementLog.occurred_at.desc()),
            rechecks,rows(ConsultationCase,ConsultationCase.requested_at.desc()),rows(FamilyRelation,FamilyRelation.id),
            rows(StageReview,StageReview.reviewed_at.desc()),rows(DoctorReview,DoctorReview.created_at.desc()),docs,
            rows(Task,Task.due_at),rows(ServiceRequest,ServiceRequest.requested_at.desc()),state,milestones,
            tuple(session.scalars(select(RiskEvent).where(RiskEvent.patient_id==member_id).order_by(RiskEvent.created_at.desc()))))

    def annual(self,session):
        members=list(session.scalars(select(Patient).order_by(Patient.display_name)))
        return [(m,self.member(session,m.id)) for m in members]

    def consultation(self,session,case_id):
        from executive_health_ai.models import Encounter
        case=session.get(ConsultationCase,case_id)
        return case,session.get(Encounter,case.encounter_id),tuple(session.scalars(select(ClinicalRecommendation).where(ClinicalRecommendation.encounter_id==case.encounter_id).order_by(ClinicalRecommendation.created_at)))


def intake_program(session, intake):
    """Legacy annual programs use their start year when cycle_year is unset."""
    from executive_health_ai.services.product_projection import current_program
    programs = list(session.scalars(select(HealthProgram).where(HealthProgram.patient_id == intake.patient_id)
                                   .order_by(HealthProgram.created_at.desc())))
    programs = [p for p in programs if (p.cycle_year or p.start_date.year) == intake.cycle_year]
    return current_program(programs) or next(iter(programs), None)


def onboarding_next(view):
    """Only the unstarted annual cycle; never replace active concrete work."""
    if not view.program or view.program.status != 'PLANNED' or view.current_phase:
        return None
    return {'资料收集中':('上传资料并处理初评例外','资料'),
        '待健管初评':('确认健管初评','初评'),
        '待医学确认':('查看医生协同进度','医疗'),
        '待补充检查':('跟进已安排的补充检查','复查'),
        '待建立基线':('建立并确认年度健康基线','基线'),
        '待制定方案':('制定阶段并启动年度方案','方案')}.get(view.onboarding)


def management_work_items(session,now):
    """Due projection runs on each queue read; no scheduler/second facts required."""
    from executive_health_ai.services.operational_worklist import OperationalWorkItem
    items=[]
    for row in session.scalars(select(IntakeAssessment).where(IntakeAssessment.status.in_(('DRAFT','SUBMITTED')),IntakeAssessment.review_status!='WAITING_MEDICAL_REVIEW')):
        program=intake_program(session,row)
        if row.status == 'DRAFT' and not program:
            continue
        draft=row.status=='DRAFT'
        items.append(OperationalWorkItem(row.patient_id,'intake_review',row.id,2,'待处理',
            '新会员资料收集与初评' if draft else '初始健康评估已提交',
            '责任健管接手：收集资料并处理初评待确认项。' if draft else '初始问卷已提交，需人工核对资料与重点。',
            '上传资料 / 处理初评例外' if draft else '完成健管确认',row.submitted_at or row.created_at,
            owner=program.owner if program else '待分配',route_target='member_management'))
    for row in session.scalars(select(RecheckPlan).where(RecheckPlan.status!='CLOSED',RecheckPlan.planned_at<=now+timedelta(days=1))):
        state={'WAITING_REPORT':'待结果','WAITING_REVIEW':'待结果','PENDING_CONFIRMATION':'待处理','TO_BOOK':'等待检查','BOOKED':'等待检查','TO_EXECUTE':'待复查','COMPLETED':'待结果'}[row.status]
        items.append(OperationalWorkItem(row.patient_id,'recheck',row.id,2,state,row.title,row.reason,'推进预约、检查、报告与复核',row.planned_at,document_id=row.document_id,owner=row.owner,route_target='member_management'))
    for row in session.scalars(select(ConsultationCase).where(ConsultationCase.status!='COMPLETED')):
        state='待处理' if row.status=='WAITING_ACTIONS' else '等待医生'
        items.append(OperationalWorkItem(row.patient_id,'consultation',row.id,2,state,'会诊方案拆解' if row.status=='WAITING_ACTIONS' else '正式会诊协同',row.conclusion or row.evidence,'健管确认行动拆解' if row.status=='WAITING_ACTIONS' else '准备资料与收集各科意见',row.scheduled_at,owner=row.owner,route_target='doctor_review'))
    reviewed=set(session.scalars(select(StageReview.phase_id)))
    for phase,program in session.execute(select(ProgramPhase,HealthProgram).join(HealthProgram,ProgramPhase.program_id==HealthProgram.id).where(HealthProgram.cycle_year.is_not(None),ProgramPhase.status=='ACTIVE')):
        ready=phase.end_date<=now.date()
        if not ready and phase.id not in reviewed:
            from executive_health_ai.services.management_action_loop import ManagementActionLoop
            state=ManagementActionLoop().project(session,program.patient_id,program.id)
            ready=bool(state['phase'] and state['phase'].id==phase.id and state['review_ready'])
        if phase.id not in reviewed and ready:
            items.append(OperationalWorkItem(program.patient_id,'stage_review',phase.id,2,'待处理','阶段复盘：'+phase.title,phase.goal,'记录阶段结果并确认下一阶段',datetime.combine(phase.end_date,time(17),now.tzinfo),owner=phase.owner or program.owner,route_target='member_management'))
    return items
