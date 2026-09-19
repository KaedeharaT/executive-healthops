"""Read-only role context; never writes health facts or assigns staff."""
from sqlalchemy import select
from executive_health_ai.models import HealthProgram, DoctorReview, ServiceRequest
from executive_health_ai.ui.experience import business_text


def care_team_context(session, patient_id):
    program = session.scalar(select(HealthProgram).where(HealthProgram.patient_id == patient_id, HealthProgram.status.in_(("ACTIVE", "PLANNED", "PAUSED"))).order_by(HealthProgram.created_at.desc()))
    review = session.scalar(select(DoctorReview).where(DoctorReview.patient_id == patient_id, DoctorReview.doctor_name.not_in(("", "待分配医生"))).order_by(DoctorReview.reviewed_at.desc(), DoctorReview.created_at.desc()))
    request = session.scalar(select(ServiceRequest).where(ServiceRequest.patient_id == patient_id, ServiceRequest.assigned_manager.is_not(None), ServiceRequest.status.not_in(("COMPLETED", "CANCELLED"))).order_by(ServiceRequest.requested_at.desc()))
    people = [("健康管理师", business_text(program.owner) if program and program.owner else "尚待确认负责人", "统筹当前计划与后续行动")]
    if review:
        people.append(("参与复核的医生", business_text(review.doctor_name), "本次医学复核记录；不代表持续签约"))
    if request and request.assigned_manager:
        people.append(("服务协调", business_text(request.assigned_manager), "跟进当前申请与安排"))
    return people
