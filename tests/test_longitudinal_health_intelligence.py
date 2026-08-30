"""Synthetic safety coverage for governed longitudinal intelligence."""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.blood_pressure import TOKYO_TIMEZONE
from executive_health_ai.models import Base, Document, HealthAssessment, Observation, Patient, ReportExtractionCandidate, ReportExtractionRun, RiskEvent
from executive_health_ai.services.longitudinal import HealthAssessmentService, HealthTimelineService, InterventionOutcomeService, OversightRiskSummaryService, ReportComparisonService, ReportRiskSummaryService


def _session():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


def _member(session):
    member = Patient(external_id="synthetic-intelligence", timezone="Asia/Tokyo"); session.add(member); session.flush(); return member


def test_confirmed_versioned_baseline_drives_timeline_snapshot():
    session = _session(); member = _member(session); service = HealthAssessmentService()
    draft = service.create_assessment(session, member.id, title="草稿", summary="synthetic", baseline={}, created_by="manager")
    baseline = service.create_initial_baseline(session, member.id, summary="synthetic baseline", baseline={"weight": 80, "source_reports": ["synthetic"]}, created_by="manager")
    assert draft.status == "DRAFT" and baseline.status == "CONFIRMED" and baseline.version == 2
    timeline = HealthTimelineService().get_timeline(session, member.id)
    assert len([item for item in timeline if item.event_type == "assessment"]) == 1
    assert timeline[0].expandable_details["weight"] == 80


def test_confirmed_report_comparison_is_objective_and_missing_is_not_resolved():
    session = _session(); member = _member(session)
    old, new = Document(patient_id=member.id, document_type="report", title="old", storage_reference="synthetic://old", source="synthetic"), Document(patient_id=member.id, document_type="report", title="new", storage_reference="synthetic://new", source="synthetic")
    session.add_all([old, new]); session.flush()
    runs = [ReportExtractionRun(document_id=item.id, patient_id=member.id, status="COMPLETED", parser_version="t", canonical_registry_version="t", file_hash=str(index), file_type="TXT") for index, item in enumerate((old, new))]
    session.add_all(runs); session.flush()
    session.add_all([ReportExtractionCandidate(extraction_run_id=runs[0].id, document_id=old.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="ldl", normalized_value="3.8", unit="mmol/L", confidence="HIGH", extraction_method="RULE", evidence_text="synthetic", status="CONFIRMED"), ReportExtractionCandidate(extraction_run_id=runs[1].id, document_id=new.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="ldl", normalized_value="4.2", unit="mmol/L", confidence="HIGH", extraction_method="RULE", evidence_text="synthetic", status="CONFIRMED"), ReportExtractionCandidate(extraction_run_id=runs[0].id, document_id=old.id, patient_id=member.id, candidate_type="FINDING", summary="synthetic finding", confidence="HIGH", extraction_method="RULE", evidence_text="synthetic", status="CONFIRMED")]); session.flush()
    result = ReportComparisonService().compare(session, member.id, old.id, new.id)
    assert result["metric_changes"][0]["status"] == "INCREASED"
    assert result["resolved_findings"] == [] and result["not_rechecked_findings"] == ["synthetic finding"]


def test_report_risk_unknown_without_rule_and_oversight_has_no_clinical_detail():
    session = _session(); member = _member(session); document = Document(patient_id=member.id, document_type="report", title="report", storage_reference="synthetic://r", source="synthetic"); session.add(document); session.flush()
    run = ReportExtractionRun(document_id=document.id, patient_id=member.id, status="COMPLETED", parser_version="t", canonical_registry_version="t", file_hash="r", file_type="TXT"); session.add(run); session.flush()
    session.add(ReportExtractionCandidate(extraction_run_id=run.id, document_id=document.id, patient_id=member.id, candidate_type="OBSERVATION", canonical_code="synthetic_metric", normalized_value="1", unit="x", confidence="HIGH", extraction_method="RULE", evidence_text="synthetic", status="CONFIRMED")); session.flush()
    assert ReportRiskSummaryService().summarize(session, member.id, document.id)["level"] == "UNKNOWN"
    oversight = OversightRiskSummaryService().summarize(session)
    assert oversight["clinical_details_included"] is False and "members" not in oversight


def test_outcome_requires_two_valid_samples_per_side():
    session = _session(); member = _member(session); pivot = datetime(2026, 1, 10, tzinfo=TOKYO_TIMEZONE)
    session.add_all([Observation(patient_id=member.id, observed_at=pivot-timedelta(days=2), metric_code="steps", value_numeric=Decimal("10"), unit="count", source="synthetic", quality_flag="valid"), Observation(patient_id=member.id, observed_at=pivot+timedelta(days=2), metric_code="steps", value_numeric=Decimal("20"), unit="count", source="synthetic", quality_flag="valid")]); session.flush()
    assert InterventionOutcomeService().compare(session, member.id, "steps", pivot, days=7)["status"] == "INSUFFICIENT_DATA"
