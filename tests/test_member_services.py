from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from executive_health_ai.models import Base, Patient, RiskEvent
from executive_health_ai.services.longitudinal import HealthTimelineService, RiskSummaryService
from executive_health_ai.services.member_services import MemberServiceOperations


def _session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_demo_service_catalog_request_completion_and_quota_are_human_operated():
    with _session() as session:
        member = Patient(external_id="synthetic-service-member", timezone="Asia/Tokyo"); session.add(member); session.flush()
        operations = MemberServiceOperations(); plan = operations.ensure_demo_plan(session, member.id)
        rows = operations.member_services(session, member.id)
        mdt, entitlement = next(row for row in rows if row[0].code == "mdt")
        request = operations.request(session, member.id, mdt.id, "需要人工审核安排")
        assert request.status == "REQUESTED" and entitlement.used_quota == 0
        operations.approve(session, request.id, "manager")
        operations.complete(session, request.id, "已完成服务，后续人工跟进。", "manager")
        assert request.status == "COMPLETED" and entitlement.used_quota == 1 and plan.status == "DEMO"
        assert any(event.event_type == "service" for event in HealthTimelineService().get_timeline(session, member.id))


def test_cancelled_service_does_not_consume_and_unknown_is_not_green():
    with _session() as session:
        member = Patient(external_id="real-uat-member", timezone="Asia/Tokyo"); session.add(member); session.flush()
        operations = MemberServiceOperations(); operations.ensure_demo_plan(session, member.id)
        item, entitlement = next(row for row in operations.member_services(session, member.id) if row[0].code == "mdt")
        request = operations.request(session, member.id, item.id, "测试"); request.status = "CANCELLED"
        assert entitlement.used_quota == 0
        assert RiskSummaryService().for_member(session, member.id)["current_risk_level"] == "UNKNOWN"


def test_member_choice_is_recorded_and_member_cannot_approve_service():
    with _session() as session:
        member = Patient(external_id="synthetic-service-choice", timezone="Asia/Tokyo"); session.add(member); session.flush()
        operations = MemberServiceOperations(); operations.ensure_demo_plan(session, member.id)
        choice = operations.record_choice(session, member.id, "希望调整")
        assert choice.member_choice == "希望调整"
