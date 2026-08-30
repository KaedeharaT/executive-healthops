"""Synthetic coverage for longitudinal HealthOps; no clinical thresholds."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import (
    Base, Document, ExternalReferral, HealthAssessment, HealthEvent,
    ManagementRule, ManagementSignal, MemberDeviceAssignment, Observation,
    Patient, ReportExtractionCandidate, ReportExtractionRun, SleepSession,
)
from executive_health_ai.services.longitudinal import (
    HealthAssessmentService, HealthDataCategoryRegistry, HealthTimelineService,
    InterventionOutcomeService, ManagementRoutingService, ReportComparisonService,
)


def _factory():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def _member(session: Session) -> Patient:
    item = Patient(external_id="synthetic-longitudinal-member", display_name="合成成员", timezone="Asia/Tokyo")
    session.add(item); session.flush(); return item


def test_sleep_stage_data_and_missing_stage_data_are_distinct() -> None:
    with _factory()() as session:
        member = _member(session)
        with_stages = SleepSession(patient_id=member.id, sleep_start=datetime(2026, 8, 10, 23, tzinfo=TOKYO_TIMEZONE), sleep_end=datetime(2026, 8, 11, 7, tzinfo=TOKYO_TIMEZONE), total_sleep_minutes=420, deep_sleep_minutes=80, rem_sleep_minutes=90, awake_minutes=20, stage_segments_json=[{"stage": "DEEP", "minutes": "80"}], source="synthetic")
        without_stages = SleepSession(patient_id=member.id, sleep_start=datetime(2026, 8, 11, 23, tzinfo=TOKYO_TIMEZONE), sleep_end=datetime(2026, 8, 12, 7, tzinfo=TOKYO_TIMEZONE), total_sleep_minutes=400, source="synthetic")
        session.add_all([with_stages, without_stages]); session.flush()
        assert with_stages.stage_segments_json and without_stages.stage_segments_json == []


def test_lifestyle_management_signal_is_not_medical_risk_event() -> None:
    with _factory()() as session:
        member = _member(session)
        rule = ManagementRule(name="合成活动管理信号", code="SYNTHETIC_ACTIVITY_MANAGEMENT", canonical_code="steps", condition_type="THRESHOLD", threshold_config={"operator": "<", "value": "1000"}, window_config={}, recommended_route="HEALTH_MANAGER", review_status="APPROVED", is_active=True, source_reference="SYNTHETIC TEST ONLY")
        observation = Observation(patient_id=member.id, observed_at=datetime.now(TOKYO_TIMEZONE), metric_code="steps", value_numeric=Decimal("500"), unit="count", source="synthetic", quality_flag="valid")
        session.add_all([rule, observation]); session.flush()
        signal = ManagementRoutingService().evaluate_observation(session, observation.id)
        assert signal is not None and signal.recommended_route == "HEALTH_MANAGER"
        assert session.scalar(select(ManagementSignal)) is signal


def test_unapproved_management_rule_does_not_route() -> None:
    with _factory()() as session:
        member = _member(session)
        session.add_all([ManagementRule(name="未审核", code="SYNTHETIC_UNAPPROVED", canonical_code="steps", threshold_config={"operator": "<", "value": "1000"}, window_config={}, recommended_route="HEALTH_MANAGER", review_status="DRAFT", is_active=True, source_reference="SYNTHETIC"), Observation(patient_id=member.id, observed_at=datetime.now(TOKYO_TIMEZONE), metric_code="steps", value_numeric=Decimal("1"), unit="count", source="synthetic", quality_flag="valid")]); session.flush()
        observation = session.scalar(select(Observation))
        assert ManagementRoutingService().evaluate_observation(session, observation.id) is None


def test_baseline_history_taxonomy_and_device_assignment() -> None:
    with _factory()() as session:
        member = _member(session); service = HealthAssessmentService()
        first = service.create_initial_baseline(session, member.id, summary="合成初始摘要", baseline={"weight": 80}, created_by="测试健管")
        second = service.create_reassessment(session, member.id, summary="合成复评摘要", baseline={"weight": 78}, created_by="测试健管")
        session.add(MemberDeviceAssignment(patient_id=member.id, provider="mock_cgm", device_category="MEDICAL_MONITOR", assignment_status="ASSIGNED", connection_status="MOCK", assigned_by="测试健管")); session.flush()
        assert first.version == 1 and second.version == 2
        assert service.compare_assessments(first, second)["weight"] == {"previous": 80, "current": 78}
        assert HealthDataCategoryRegistry.classify_metric("steps")[0] == "ACTIVITY"
        assert session.scalar(select(MemberDeviceAssignment)).connection_status == "MOCK"


def test_report_comparison_and_longitudinal_timeline_are_source_derived() -> None:
    with _factory()() as session:
        member = _member(session)
        old_doc = Document(patient_id=member.id, document_type="report", title="合成报告A", storage_reference="synthetic://a", source="synthetic")
        new_doc = Document(patient_id=member.id, document_type="report", title="合成报告B", storage_reference="synthetic://b", source="synthetic")
        session.add_all([old_doc, new_doc]); session.flush()
        old_run = ReportExtractionRun(document_id=old_doc.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash="a", file_type="TXT")
        new_run = ReportExtractionRun(document_id=new_doc.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash="b", file_type="TXT")
        session.add_all([old_run, new_run]); session.flush()
        session.add_all([
            ReportExtractionCandidate(extraction_run_id=old_run.id, document_id=old_doc.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="ldl", normalized_value="3.8", unit="mmol/L", confidence="HIGH", extraction_method="RULE", evidence_text="合成 LDL 3.8", status="CONFIRMED"),
            ReportExtractionCandidate(extraction_run_id=new_run.id, document_id=new_doc.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="ldl", normalized_value="4.2", unit="mmol/L", confidence="HIGH", extraction_method="RULE", evidence_text="合成 LDL 4.2", status="CONFIRMED"),
            ReportExtractionCandidate(extraction_run_id=new_run.id, document_id=new_doc.id, patient_id=member.id, candidate_type="FINDING", summary="合成检查结论", confidence="MEDIUM", extraction_method="LLM", evidence_text="合成检查结论", status="CONFIRMED"),
        ])
        service = HealthAssessmentService(); service.create_initial_baseline(session, member.id, summary="合成基线", baseline={}, created_by="测试")
        session.add(HealthEvent(patient_id=member.id, start_at=datetime.now(TOKYO_TIMEZONE), event_type="surgery", description="合成手术记录", source="synthetic")); session.flush()
        comparison = ReportComparisonService().compare(session, member.id, old_doc.id, new_doc.id)
        assert round(comparison["metric_changes"][0]["delta"], 2) == 0.4
        timeline = HealthTimelineService().get_timeline(session, member.id)
        assert any(item.event_type == "assessment" for item in timeline) and any(item.event_type == "surgery" for item in timeline)


def test_intervention_before_after_is_descriptive_only() -> None:
    with _factory()() as session:
        member = _member(session); pivot = datetime(2026, 8, 15, tzinfo=TOKYO_TIMEZONE)
        session.add_all([Observation(patient_id=member.id, observed_at=pivot - timedelta(days=5), metric_code="sleep_duration", value_numeric=Decimal("300"), unit="minutes", source="synthetic", quality_flag="valid"), Observation(patient_id=member.id, observed_at=pivot - timedelta(days=3), metric_code="sleep_duration", value_numeric=Decimal("310"), unit="minutes", source="synthetic", quality_flag="valid"), Observation(patient_id=member.id, observed_at=pivot + timedelta(days=3), metric_code="sleep_duration", value_numeric=Decimal("380"), unit="minutes", source="synthetic", quality_flag="valid"), Observation(patient_id=member.id, observed_at=pivot + timedelta(days=5), metric_code="sleep_duration", value_numeric=Decimal("390"), unit="minutes", source="synthetic", quality_flag="valid")]); session.flush()
        summary = InterventionOutcomeService().compare(session, member.id, "sleep_duration", pivot, days=30)
        assert summary and summary["difference"] == 80 and "不代表因果" in summary["label"]
