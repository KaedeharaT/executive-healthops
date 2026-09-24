"""One report-ingestion hook, using the existing event service and supervisor."""
from executive_health_ai.services.event_service import EventService
from executive_health_ai.services.product_projection import ProductProjectionService
from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.agent.post_checkup import VERSION
from executive_health_ai.models.base import utc_now


def report_ingested(session, report, actor):
    program = ProductProjectionService().member(session, report.patient_id).program
    event, _ = EventService().publish(session, event_type='REPORT_UPLOADED', member_id=report.patient_id,
        source_type='document', source_id=str(report.id), payload_summary='新体检报告已进入健康管理流程',
        metadata={'workflow': VERSION, 'member_id': str(report.patient_id), 'report_id': str(report.id),
                  'annual_cycle_id': str(program.id) if program else None, 'triggered_at': utc_now().isoformat(), 'actor': actor})
    return HealthOpsAgentSupervisor().receive_event(session, event)
