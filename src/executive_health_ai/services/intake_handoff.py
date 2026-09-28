"""Continue a recognized, reviewed report into the existing post-checkup policy."""
from uuid import UUID
from sqlalchemy import select
from executive_health_ai.models import Document,ReportExtractionCandidate,HealthEvent


def report_ready(session,profile_goal):
    document=session.get(Document,UUID(profile_goal.source_id))
    if not document or document.patient_id!=profile_goal.member_id:return
    report=document.document_type=='health_check_report' or (
        document.document_type=='auto' and any(t in document.title.lower() for t in ('体检','checkup','check-up')))
    if not report:return
    confirmed=session.scalar(select(ReportExtractionCandidate.id).where(
        ReportExtractionCandidate.document_id==document.id,ReportExtractionCandidate.candidate_type=='OBSERVATION',
        ReportExtractionCandidate.status.in_(('PENDING_REVIEW','CONFIRMED','CORRECTED'))).limit(1))
    if not confirmed:return
    document.document_type='health_check_report'
    prior=session.scalar(select(HealthEvent).where(HealthEvent.member_id==document.patient_id,
        HealthEvent.event_type=='CHECKUP_REPORT_UPLOADED',HealthEvent.source_id==str(document.id)))
    if prior:return prior,False
    from executive_health_ai.services.health_events import ingest_health_event
    return ingest_health_event(session,member_id=document.patient_id,event_type='CHECKUP_REPORT_UPLOADED',
        event_category='NEW_INFORMATION',source_type='SYSTEM',source_id=str(document.id),
        payload_ref={'metadata':{'uploaded_by':profile_goal.owner,'workflow':'post_checkup_v1'},
            'intake_goal_id':str(profile_goal.id)})
