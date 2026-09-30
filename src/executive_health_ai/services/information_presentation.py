"""Read-only facts for structured UI; no new workflow or medical decisions."""
from sqlalchemy import select
from executive_health_ai.models import HealthProgram, ProgramPhase, Task, HealthProblem, ServiceRequest, ServiceCatalogItem
from executive_health_ai.models.management_workflow import ManagementLog, IntakeAssessment
from executive_health_ai.services.product_projection import current_program


def member_directory(session, members, *, include_archived=False):
    from executive_health_ai.services.member_archive import active_ids
    active=set(session.scalars(active_ids()))
    members=[m for m in members if include_archived or m.id in active]
    ids = [m.id for m in members]
    if not ids:
        return []
    programs = list(session.scalars(select(HealthProgram).where(HealthProgram.patient_id.in_(ids)).order_by(HealthProgram.created_at.desc())))
    phases = list(session.scalars(select(ProgramPhase).where(ProgramPhase.program_id.in_([p.id for p in programs]), ProgramPhase.status == 'ACTIVE')))
    logs = list(session.scalars(select(ManagementLog).where(ManagementLog.patient_id.in_(ids)).order_by(ManagementLog.occurred_at.desc())))
    tasks = list(session.scalars(select(Task).where(Task.patient_id.in_(ids), Task.status.not_in(('COMPLETED','CANCELLED'))).order_by(Task.due_at.asc().nulls_last(), Task.created_at)))
    problems = list(session.scalars(select(HealthProblem).where(HealthProblem.patient_id.in_(ids), HealthProblem.status != 'CLOSED')))
    assessments = list(session.scalars(select(IntakeAssessment).where(IntakeAssessment.patient_id.in_(ids))))
    services=list(session.scalars(select(ServiceRequest).where(ServiceRequest.patient_id.in_(ids),ServiceRequest.status.not_in(('COMPLETED','CANCELLED')))))
    names={r.id:r.name for r in session.scalars(select(ServiceCatalogItem))}
    result = []
    for member in members:
        program = current_program([p for p in programs if p.patient_id == member.id])
        phase = next((p for p in phases if program and p.program_id == program.id), None)
        task = next((t for t in tasks if t.patient_id == member.id), None)
        log = next((r for r in logs if r.patient_id == member.id), None)
        intake = next((a for a in assessments if a.patient_id == member.id and program and a.cycle_year == (program.cycle_year or program.start_date.year)), None)
        focus = (intake.professional_focus if intake else '') or '；'.join(p.title for p in problems if p.patient_id == member.id)
        current_services='、'.join(dict.fromkeys(names.get(r.service_item_id,'健康服务') for r in services if r.patient_id==member.id)) or '暂无开放服务'
        result.append(dict(member=member, program=program, phase=phase, task=task, log=log, focus=focus,service=current_services))
    return result
