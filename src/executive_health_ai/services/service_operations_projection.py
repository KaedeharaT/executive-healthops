"""Business views of existing service/plan records; no new workflow or facts."""
from sqlalchemy import select
from executive_health_ai.models import HealthProgram, ProgramPhase, Task, OutcomeEvaluation, DoctorReview
from executive_health_ai.services.member_archive import active_ids

SERVICE_STAGES = ('待安排', '已预约', '执行中', '待回访', '待结果确认', '已完成')
CLOSED = {'COMPLETED', 'CANCELLED', 'CLOSED'}


def service_stage(request, tasks, logs=()):
    if request.status == 'CANCELLED':
        return '已取消'
    if request.status in {'REQUESTED', 'REVIEWING', 'APPROVED'}:
        return '待安排'
    if request.status == 'SCHEDULED':
        return '已预约'
    if request.status in {'IN_PROGRESS', 'IN_SERVICE'}:
        return '执行中'
    if request.status == 'COMPLETED':
        if not request.result_summary or any(t.patient_id == request.patient_id and
                t.source == f'service_result:{request.id}' and t.status not in CLOSED for t in tasks):
            return '待结果确认'
        result_ids = {t.id for t in tasks if t.patient_id == request.patient_id and t.source == f'service_result:{request.id}'}
        followups = set()
        while True:
            found = {log.follow_up_task_id for log in logs if log.follow_up_task_id and log.patient_id == request.patient_id and
                (log.related_service_id == request.id or log.related_task_id in result_ids | followups)}
            if found <= followups:
                break
            followups |= found
        if any(t.id in followups and t.status not in CLOSED for t in tasks):
            return '待回访'
        return '已完成'
    return '待核对'


def service_context(session, request):
    program = session.get(HealthProgram, request.program_id) if request.program_id else None
    phase = session.get(ProgramPhase, request.phase_id) if request.phase_id else None
    return {'plan': program.title if program else '未关联方案',
            'phase': phase.title if phase else '年度周期 / 待关联阶段',
            'owner': request.assigned_manager or (program.owner if program else None) or '待分配'}


def service_next(request, tasks, logs=()):
    stage = service_stage(request,tasks,logs)
    return {'已完成':'结果已确认，继续阶段复盘与后续安排',
            '待结果确认':'健管复核服务结果与完成依据',
            '待回访':'执行已约定回访并记录会员反馈',
            '已取消':'保留取消原因；如仍有需要，重新申请'}.get(stage,request.next_action or '核对安排')


def special_programs(session):
    """One row per recorded program/metric, latest evidence, no inferred target."""
    programs = list(session.scalars(select(HealthProgram).where(HealthProgram.patient_id.in_(active_ids()))))
    rows = []
    for program in programs:
        phase = session.scalar(select(ProgramPhase).where(ProgramPhase.program_id == program.id,
            ProgramPhase.status == 'ACTIVE').order_by(ProgramPhase.sequence))
        tasks = list(session.scalars(select(Task).where(Task.program_id == program.id)))
        outcomes = list(session.scalars(select(OutcomeEvaluation).where(OutcomeEvaluation.program_id == program.id)
            .order_by(OutcomeEvaluation.evaluation_date.desc(), OutcomeEvaluation.created_at.desc(), OutcomeEvaluation.id.desc())))
        latest = {}
        for row in outcomes:
            latest.setdefault(row.metric, row)
        open_tasks = sorted((t for t in tasks if t.status not in CLOSED), key=lambda t:(t.due_at is None, t.due_at))
        for outcome in latest.values():
            rows.append(dict(program=program, phase=phase, outcome=outcome,
                completed=sum(t.status == 'COMPLETED' for t in tasks), total=sum(t.status != 'CANCELLED' for t in tasks),
                next=open_tasks[0] if open_tasks else None))
    return rows


def stage_evidence(session, member_id, program_id, phase):
    if not phase:
        return {}
    outcomes = session.scalars(select(OutcomeEvaluation).where(OutcomeEvaluation.patient_id == member_id,
        OutcomeEvaluation.program_id == program_id, OutcomeEvaluation.evaluation_date >= phase.start_date,
        OutcomeEvaluation.evaluation_date <= phase.end_date).order_by(OutcomeEvaluation.evaluation_date))
    from executive_health_ai.services.health_visualization import metric_label
    metrics = [f'{metric_label(o.metric)}：{o.baseline_value} → {o.current_value} {o.unit}；'
        f'{o.evaluation_date}；依据：{o.evidence}' for o in outcomes]
    doctors = session.scalars(select(DoctorReview).where(DoctorReview.patient_id == member_id,
        DoctorReview.program_id == program_id, DoctorReview.status == 'CONFIRMED'))
    opinions = [f'{d.doctor_name}：{d.opinion}' for d in doctors if d.opinion]
    return {'关键指标变化':'；'.join(metrics) or '本阶段尚无已记录指标结果；资料不足，不推断改善',
            '医生意见':'；'.join(opinions) or '本方案暂无已确认医生意见'}
