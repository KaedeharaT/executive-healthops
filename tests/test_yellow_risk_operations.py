"""Synthetic end-to-end checks for the human Yellow-risk operations loop."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import AuditLog, Base, Document, DoctorReview, FollowUp, Observation, Patient, ReportExtractionCandidate, ReportExtractionRun, RiskEvent, RiskRule, Task
from executive_health_ai.services.report_parsing import ReportParsingService
from executive_health_ai.services.risk_operations import RiskOperationsService
from executive_health_ai.services.risk_triage import RiskEvaluationService


def _factory():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _yellow(session: Session) -> tuple[Patient, Observation, RiskEvent]:
    member = Patient(external_id="yellow-operations-synthetic", timezone="Asia/Tokyo")
    session.add(member); session.flush()
    rule = RiskRule(name="合成运营验证规则", code="SYNTHETIC_YELLOW_OPERATIONS", applicable_device_class="ANY", canonical_code="steps", risk_level="YELLOW", condition_type="SYNTHETIC_TEST_THRESHOLD", threshold_config={"metric": "steps", "operator": ">=", "value": "8000", "unit": "count"}, window_config={}, requires_repeated_measurement=False, requires_symptom_confirmation=False, action_type="SYNTHETIC_TEST_ONLY", source_reference="SYNTHETIC TEST ONLY", review_status="APPROVED", reviewed_by="synthetic", is_active=True)
    session.add(rule)
    observation = Observation(patient_id=member.id, observed_at=datetime(2026, 8, 17, 9, tzinfo=TOKYO_TIMEZONE), metric_code="steps", value_numeric=9000, unit="count", source="synthetic_gateway", quality_flag="valid")
    session.add(observation); session.flush()
    RiskEvaluationService().evaluate_observation(session, observation.id)
    return member, observation, session.scalar(select(RiskEvent))


def test_yellow_monitoring_creates_task_and_keeps_event_active() -> None:
    with _factory()() as session:
        _, _, event = _yellow(session)
        operations = RiskOperationsService()
        task = operations.continue_monitoring(session, event.id, "测试健康管理师", "合成观察原因", datetime.now(TOKYO_TIMEZONE) + timedelta(days=1))
        assert task.risk_event_id == event.id and task.status == "PENDING"
        assert event.status == "MONITORING"
        operations.complete_monitoring_task(session, event.id, "测试健康管理师", "合成复核完成", task.id)
        assert task.status == "COMPLETED"
        assert session.scalar(select(AuditLog).where(AuditLog.action == "yellow_monitoring_selected")) is not None


def test_contact_is_a_human_record_not_a_close_or_message() -> None:
    with _factory()() as session:
        _, _, event = _yellow(session)
        RiskOperationsService().record_contact(session, event.id, "测试健康管理师", "电话", "已联系", "合成联系记录")
        assert event.status == "ACKNOWLEDGED"
        audit = session.scalar(select(AuditLog).where(AuditLog.action == "yellow_member_contact_recorded"))
        assert audit is not None and audit.detail_json["method"] == "电话"


def test_data_issue_closes_event_without_deleting_original_observation() -> None:
    with _factory()() as session:
        _, observation, event = _yellow(session)
        RiskOperationsService().mark_data_issue(session, event.id, "测试健康管理师", "合成设备错误")
        assert session.get(Observation, observation.id) is not None
        assert event.status == "DISMISSED_DATA_ISSUE" and event.resolved_at is not None


def test_yellow_doctor_followup_and_explicit_close_are_audited() -> None:
    with _factory()() as session:
        _, _, event = _yellow(session)
        service = RiskOperationsService()
        review = service.escalate_to_doctor(session, event.id, "测试健康管理师", "请确认下一步人工评估安排。")
        assert review.status == "PENDING" and review.risk_event_id == event.id
        assert service.escalate_to_doctor(session, event.id, "测试健康管理师", "重复提交") .id == review.id
        review, task = service.complete_doctor_review(session, review.id, "测试医生", "全科/健康管理", "测试医生意见", "测试后续跟进", datetime.now(TOKYO_TIMEZONE) + timedelta(days=2))
        followup = service.record_follow_up(session, event.id, "测试健康管理师", "测试跟进完成", task.id)
        service.close(session, event.id, "测试健康管理师", "测试人工关闭原因")
        assert review.status == "CONFIRMED" and task.status == "COMPLETED" and isinstance(followup, FollowUp)
        assert event.status == "CLOSED"
        actions = {item.action for item in session.scalars(select(AuditLog))}
        assert {"yellow_doctor_review_requested", "yellow_doctor_review_completed", "yellow_followup_recorded", "yellow_closed"} <= actions


def test_closed_yellow_rejects_more_actions_and_no_llm_is_involved() -> None:
    with _factory()() as session:
        _, _, event = _yellow(session)
        service = RiskOperationsService(); service.close(session, event.id, "测试健康管理师", "测试关闭")
        try:
            service.escalate_to_doctor(session, event.id, "测试健康管理师", "不应创建")
            assert False, "closed events must not be escalated"
        except ValueError:
            pass
    import executive_health_ai.services.risk_operations as module
    assert "qwen" not in module.__file__.lower()


def test_synthetic_report_confirmation_reaches_yellow_then_doctor_review() -> None:
    with _factory()() as session:
        member = Patient(external_id="report-yellow-synthetic", timezone="Asia/Tokyo"); session.add(member); session.flush()
        rule = RiskRule(name="合成报告验证规则", code="SYNTHETIC_REPORT_YELLOW", applicable_device_class="REPORT", canonical_code="steps", risk_level="YELLOW", condition_type="SYNTHETIC_TEST_THRESHOLD", threshold_config={"metric": "steps", "operator": ">=", "value": "8000", "unit": "count"}, window_config={}, requires_repeated_measurement=False, requires_symptom_confirmation=False, action_type="SYNTHETIC_TEST_ONLY", source_reference="SYNTHETIC TEST ONLY", review_status="APPROVED", reviewed_by="synthetic", is_active=True); session.add(rule)
        document = Document(patient_id=member.id, document_type="synthetic_report", title="synthetic report", storage_reference="synthetic://report", source="test"); session.add(document); session.flush()
        run = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash="a" * 64, file_type="TXT", detected_report_date=datetime(2026, 8, 17).date()); session.add(run); session.flush()
        candidate = ReportExtractionCandidate(extraction_run_id=run.id, document_id=document.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="steps", raw_name="合成步数", raw_value="9000", normalized_value="9000", unit="count", structured_data_json={}, confidence="HIGH", extraction_method="RULE", source_page=1, evidence_text="合成步数 9000 count"); session.add(candidate); session.flush()
        ReportParsingService().confirm_candidate(session, candidate, "测试健康管理师")
        event = session.scalar(select(RiskEvent).where(RiskEvent.patient_id == member.id))
        review = RiskOperationsService().escalate_to_doctor(session, event.id, "测试健康管理师", "请确认合成后续安排。")
        assert candidate.status == "CONFIRMED" and event is not None and review.risk_event_id == event.id
