"""Deep invariants for annual, frozen and evidence-bound health baselines."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.agent.supervisor import HealthOpsAgentSupervisor
from executive_health_ai.models import (
    AgentApprovalRequest, AgentPlanStep, Base, Document, HealthAssessment,
    HealthEvent, HealthProblem, MedicationPlan, Observation, Patient,
    ReportExtractionCandidate, ReportExtractionRun, RiskEvent,
)
from executive_health_ai.services.event_service import EventService
from executive_health_ai.services.longitudinal import HealthAssessmentService, ReportComparisonService


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _member(session: Session, name: str = "baseline-deep") -> Patient:
    member = Patient(external_id=name, timezone="Asia/Tokyo")
    session.add(member); session.flush()
    return member


def _report(session: Session, member: Patient, title: str, code: str, value: str) -> Document:
    document = Document(patient_id=member.id, document_type="health_check_report", title=title, storage_reference=f"synthetic://{title}", source="test")
    session.add(document); session.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="test", canonical_registry_version="test", file_hash=str(document.id), file_type="TXT")
    session.add(run); session.flush()
    candidate = ReportExtractionCandidate(
        extraction_run_id=run.id, document_id=document.id, patient_id=member.id,
        candidate_type="OBSERVATION", canonical_code=code, normalized_value=value,
        unit="mmol/L", confidence="HIGH", extraction_method="RULE",
        evidence_text=f"{code} {value}", source_page=2, status="CONFIRMED",
    )
    session.add(candidate); session.flush()
    session.add(Observation(
        patient_id=member.id, observed_at=datetime.now(timezone.utc), metric_code=code,
        value_numeric=Decimal(value), unit="mmol/L", source="confirmed_health_check_report",
        source_record_id=str(candidate.id), quality_flag="valid",
    ))
    session.flush()
    return document


def test_multiple_intake_reports_merge_once_and_confirmed_snapshot_is_frozen() -> None:
    session = _session(); member = _member(session)
    first = _report(session, member, "年度总检", "ldl", "4.15")
    second = _report(session, member, "补充血液检查", "hba1c", "6.3")
    service = HealthAssessmentService()
    draft = service.create_draft_from_report(session, member.id, first.id, created_by="manager", cycle_year=2026)
    same = service.create_draft_from_report(session, member.id, second.id, created_by="manager", cycle_year=2026)
    assert same.id == draft.id
    assert len(draft.baseline_json["source_reports"]) == 2
    assert {row["metric"] for row in draft.baseline_json["key_metrics"]} == {"ldl", "hba1c"}
    confirmed = service.confirm(session, draft.id, "manager")
    frozen = deepcopy(confirmed.baseline_json)
    session.add(Observation(patient_id=member.id, observed_at=datetime.now(timezone.utc), metric_code="ldl", value_numeric=Decimal("3.60"), unit="mmol/L", source="device", quality_flag="valid")); session.flush()
    assert confirmed.baseline_json == frozen
    assert Decimal(service.current_profile(session, member.id)["latest_metrics"]["ldl"]["value"]) == Decimal("3.60")


def test_manual_no_report_baseline_missing_data_and_doctor_boundary() -> None:
    session = _session(); member = _member(session, "manual-baseline")
    service = HealthAssessmentService()
    draft = service.create_manual_draft(
        session, member.id, created_by="manager", summary="缺少年度体检，先整理现有资料。",
        intake={"既往史": "成员自述待核对"}, cycle_year=2026, medical_review_required=True,
    )
    assert service.create_manual_draft(
        session, member.id, created_by="manager", summary="页面刷新不应重复创建", cycle_year=2026,
    ).id == draft.id
    assert draft.baseline_json["data_coverage"]["年度体检"] == "缺少年度体检"
    with pytest.raises(ValueError, match="医生复核"):
        service.confirm(session, draft.id, "manager")
    assert draft.status == "WAITING_MEDICAL_REVIEW"
    service.mark_medical_reviewed(session, draft.id, doctor="licensed-doctor")
    confirmed = service.confirm(session, draft.id, "manager")
    assert confirmed.status == "CONFIRMED" and confirmed.medical_reviewed_by == "licensed-doctor"


def test_correction_creates_amendment_and_never_overwrites_original() -> None:
    session = _session(); member = _member(session, "amendment")
    service = HealthAssessmentService()
    draft = service.create_manual_draft(session, member.id, created_by="manager", summary="人工初稿", cycle_year=2026)
    draft.baseline_json = {**draft.baseline_json, "key_metrics": [{"metric": "hba1c", "value": "5.0", "unit": "%"}]}
    original = service.confirm(session, draft.id, "manager")
    original_snapshot = deepcopy(original.baseline_json)
    amended = service.amend_baseline(
        session, original.id,
        changes={"key_metrics": [{"metric": "glucose", "value": "5.0", "unit": "mmol/L"}]},
        reason="原字段映射错误", amended_by="manager",
        evidence_references={"document": "人工复核的原始报告第2页"},
    )
    assert original.baseline_json == original_snapshot and original.status == "SUPERSEDED"
    assert amended.status == "AMENDED" and amended.version == 2
    assert amended.parent_assessment_id == original.id and amended.snapshot_hash != original.snapshot_hash


def test_next_annual_cycle_is_new_unconfirmed_reference_point() -> None:
    session = _session(); member = _member(session, "next-cycle")
    service = HealthAssessmentService()
    prior = service.create_manual_draft(session, member.id, created_by="manager", summary="2026初稿", cycle_year=2026)
    prior.baseline_json = {**prior.baseline_json, "health_problems": [{"title": "长期健康问题", "source_entity_id": "synthetic"}]}
    service.confirm(session, prior.id, "manager")
    next_draft = service.create_next_cycle_draft(session, member.id, next_year=2027, created_by="manager")
    assert next_draft.cycle_year == 2027 and next_draft.version == 1 and next_draft.status == "DRAFT"
    assert next_draft.baseline_json["inherited_context"]["status"] == "PENDING_RECONFIRMATION"
    assert service.latest_baseline(session, member.id, include_draft=False, cycle_year=2026).id == prior.id


def test_baseline_and_report_comparisons_are_explicit_and_nonclinical() -> None:
    session = _session(); member = _member(session, "comparison")
    first = _report(session, member, "年度报告", "ldl", "4.15")
    service = HealthAssessmentService(); draft = service.create_draft_from_report(session, member.id, first.id, created_by="manager", cycle_year=2026)
    service.confirm(session, draft.id, "manager")
    second = _report(session, member, "季度复查", "ldl", "3.60")
    baseline_result = ReportComparisonService().compare_to_baseline(session, member.id, cycle_year=2026)
    report_result = ReportComparisonService().compare(session, member.id, first.id, second.id)
    assert baseline_result["comparison_type"] == "BASELINE_TO_CURRENT"
    assert baseline_result["changes"][0]["status"] == "CHANGED"
    assert baseline_result["changes"][0]["status"] not in {"IMPROVED", "WORSENED"}
    assert "不自动判断" in baseline_result["interpretation"]
    assert report_result["comparison_type"] == "REPORT_TO_REPORT"


def test_agent_waits_for_baseline_confirmed_before_risk_evaluation() -> None:
    session = _session(); member = _member(session, "agent-baseline-wait")
    report = _report(session, member, "体检报告", "ldl", "4.15")
    supervisor = HealthOpsAgentSupervisor()
    uploaded, _ = EventService().publish(session, event_type="REPORT_UPLOADED", member_id=member.id, source_type="document", source_id=report.id)
    goal = supervisor.receive_event(session, uploaded)
    confirmed, _ = EventService().publish(session, event_type="REPORT_CONFIRMED", member_id=member.id, source_type="document", source_id=report.id)
    supervisor.receive_event(session, confirmed)
    assert goal.current_stage == "等待健康基线确认"
    assert session.query(RiskEvent).count() == 0
    waiting = session.scalar(select(AgentPlanStep).where(AgentPlanStep.plan_id == goal.current_plan_id, AgentPlanStep.wait_event_type == "BASELINE_CONFIRMED"))
    assert waiting.status == "WAITING_MANAGER"
    draft = HealthAssessmentService().create_draft_from_report(session, member.id, report.id, created_by="manager")
    HealthAssessmentService().confirm(session, draft.id, "manager")
    event, _ = EventService().publish(session, event_type="BASELINE_CONFIRMED", member_id=member.id, source_type="health_assessment", source_id=draft.id)
    supervisor.receive_event(session, event)
    approval = session.scalar(select(AgentApprovalRequest).where(AgentApprovalRequest.goal_id == goal.id, AgentApprovalRequest.status == "PENDING"))
    assert goal.current_stage == "等待健康管理师接手" and approval is not None


def test_ai_cannot_confirm_or_create_a_confirmed_baseline() -> None:
    session = _session(); member = _member(session, "ai-boundary")
    service = HealthAssessmentService()
    with pytest.raises(PermissionError):
        service.create_assessment(session, member.id, title="非法", summary="AI", baseline={}, created_by="ai", confirmed=True)
    draft = service.create_manual_draft(session, member.id, created_by="manager", summary="人工初稿")
    with pytest.raises(PermissionError):
        service.confirm(session, draft.id, "model", reviewer_role="AI")


def test_continuous_data_snapshot_marks_stale_data_and_keeps_a_window_summary() -> None:
    session = _session(); member = _member(session, "stale-data")
    old = Observation(
        patient_id=member.id, observed_at=datetime.now(timezone.utc) - timedelta(days=75),
        metric_code="steps", value_numeric=Decimal("6200"), unit="count",
        source="device", quality_flag="valid",
    )
    session.add(old); session.flush()
    rows, coverage = HealthAssessmentService()._continuous_data_snapshot([old], {"steps"})
    assert rows[0]["status"] == "STALE" and rows[0]["sample_count"] == 0
    assert coverage["运动"] == "数据时间较早"
    assert "value" not in rows[0]


def test_manual_draft_aggregates_confirmed_history_medication_procedure_and_device_summary() -> None:
    session = _session(); member = _member(session, "multi-source")
    problem = HealthProblem(patient_id=member.id, title="已确认健康问题", description="人工记录", status="OPEN", severity="MEDIUM", source="doctor_record")
    medication = MedicationPlan(
        patient_id=member.id, drug_name="已记录用药", dose="1", dose_unit="片",
        frequency="每日", route="口服", start_date=datetime.now(timezone.utc).date(),
        prescriber_name="医生", status="active",
    )
    procedure = HealthEvent(patient_id=member.id, start_at=datetime.now(timezone.utc) - timedelta(days=300), event_type="surgery", description="既往手术记录", source="medical_record")
    device = Observation(patient_id=member.id, observed_at=datetime.now(timezone.utc), metric_code="steps", value_numeric=Decimal("8000"), unit="count", source="device", quality_flag="valid")
    session.add_all([problem, medication, procedure, device]); session.flush()
    draft = HealthAssessmentService().create_manual_draft(
        session, member.id, created_by="manager", summary="多来源人工初稿",
        intake={"生活方式资料": "每周规律活动"}, cycle_year=2026,
    )
    assert draft.baseline_json["health_problems"][0]["source_entity_id"] == str(problem.id)
    assert draft.baseline_json["current_medications"][0]["source_entity_id"] == str(medication.id)
    assert draft.baseline_json["procedures_or_hospitalizations"][0]["source_entity_id"] == str(procedure.id)
    assert draft.baseline_json["recent_health_data"][0]["sample_count"] == 1
    assert draft.baseline_json["data_coverage"]["运动"] == "数据不足"
