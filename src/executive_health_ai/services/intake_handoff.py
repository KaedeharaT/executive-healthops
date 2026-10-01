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


def assessment_confirmed(session,row,actor):
    """A committed human decision resumes the same bounded intake capabilities.

    Called within the existing submission transaction: no external I/O. A retry
    uses the assessment identity, so it cannot repeat the completion side effect.
    """
    from executive_health_ai.services.health_events import ingest_health_event
    from executive_health_ai.services.assessment_import import digest
    revision=confirmation_revision(row)
    return ingest_health_event(session,member_id=row.patient_id,event_type='INTAKE_ASSESSMENT_CONFIRMED',
        event_category='NEW_INFORMATION',source_type='SYSTEM',source_id=str(row.id)+':'+digest(revision),
        payload_ref={'actor':actor,'assessment_id':str(row.id),'confirmation_revision':revision})


def confirmation_revision(row):
    from datetime import timezone
    at=row.submitted_at
    if at is None:raise ValueError('初评尚未完成总确认。')
    return at.replace(tzinfo=timezone.utc).isoformat() if at.tzinfo is None else at.astimezone(timezone.utc).isoformat()


def resume_confirmed_assessment(session,event):
    from executive_health_ai.models.management_workflow import IntakeAssessment
    from executive_health_ai.services.assessment_import import AssessmentImportService
    from executive_health_ai.agent.profile_intake import trace
    row=session.get(IntakeAssessment,UUID((event.payload_ref or {}).get('assessment_id',event.source_id)))
    if not row or row.patient_id!=event.member_id or row.status not in {'SUBMITTED','CONFIRMED'}:
        raise ValueError('初评尚未完成总确认。')
    saved=(row.review or {}).get('exception_intake',{})
    if not saved.get('completed_at') or not saved.get('confirmed_by'):
        raise ValueError('初评缺少健管确认记录。')
    service=AssessmentImportService();goals=service.goals(session,row)
    for goal in goals:
        if goal.status not in {'COMPLETED','CANCELLED'}:
            trace(session,goal,'健管已完成必要例外并总确认，继续原资料整理流程。',
                action='intake_confirmation_resume',health_event_id=str(event.id))
    service.finish(session,row,saved['confirmed_by'])
    return goals[0] if goals else None
